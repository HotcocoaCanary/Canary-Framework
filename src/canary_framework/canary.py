"""Canary ASGI Application Container.

This module provides the central Canary class which acts as the dependency injection
container, lifecycle manager, and ASGI application entry point.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.routing import Router as StarletteRouter
from starlette.types import Receive, Scope, Send

from canary_framework.common import (
    CanaryConfig,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)
from canary_framework.common.logging import ensure_logging, get_logger
from canary_framework.core.dependencies import resolve_deps, topological_sort
from canary_framework.core.params import resolve_endpoint_meta
from canary_framework.core.registry import Registry
from canary_framework.core.web.router import Router as _Router
from canary_framework.core.web.router import _build_doc_routes, _collect_routes

_log = get_logger("canary")


def _wire_service(inst: object, registry: Registry) -> None:
    """Inject dependencies into the instance based on type hints."""
    for attr_name, dep_cls in resolve_deps(type(inst)).items():
        setattr(inst, attr_name, registry.get_by_class(dep_cls).instance)


class Canary:
    """The central application container for Canary Framework.

    Handles dependency injection, lifecycle hooks, routing, OpenAPI generation,
    and acts as the ASGI entry point.
    """

    def __init__(self, root: object | type) -> None:
        """Initialize the Canary container with a root module.

        Args:
            root: The root module class or instance.
        """
        if isinstance(root, type):
            self._root_inst = root()
            self._root_cls = root
        else:
            self._root_inst = root
            self._root_cls = type(root)

        if not is_cf_module(self._root_cls) and not is_cf_service(self._root_cls):
            raise TypeError(
                f"Root '{self._root_cls.__name__}' must be decorated with @module or @service."
            )

        self._registry = Registry()
        self._startup_order: list[str] = []
        self._config = CanaryConfig()
        self._openapi_lock = asyncio.Lock()
        self._doc_routes: list[Route] = []

        # 1. Setup Logging & Config
        meta = get_module_meta(self._root_cls)
        if meta and meta.config_cls:
            self._config = meta.config_cls()
        ensure_logging(self._config.log_level)
        _log.info("Initializing Canary application with root module: %s", self._root_cls.__name__)

        # 2. Build Dependency Registry
        self._register_entry_with_deps(self._root_cls, self._registry)
        self._startup_order = topological_sort(self._registry)

        # 3. Instantiate Services
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            if entry.cls is self._root_cls:
                entry.instance = self._root_inst
            else:
                entry.instance = entry.cls()
            cls_name = entry.cls.__name__
            if not cls_name.startswith("_cf_"):
                setattr(self, cls_name, entry.instance)

        # 4. Wire Dependencies
        for name in self._startup_order:
            inst = self._registry.get_by_name(name).instance
            if inst is not None:
                _wire_service(inst, self._registry)
                # Inject config if available
                if not hasattr(inst, "_cf_config") or inst._cf_config is None:
                    with contextlib.suppress(AttributeError):
                        inst._cf_config = self._config  # type: ignore[attr-defined]

        # 5. Execute init() hooks
        for name in self._startup_order:
            inst = self._registry.get_by_name(name).instance
            if hasattr(inst, "init") and callable(inst.init):
                inst.init()

        # 6. Build ASGI Router
        self._asgi_app = self._build_asgi_app()

    def _register_entry_with_deps(self, cls: type, registry: Registry) -> None:
        """Recursively register a class and its dependencies."""
        if registry.has(cls):
            return

        if is_cf_module(cls):
            meta = get_module_meta(cls)
            registry.register(cls, meta=meta)  # type: ignore
            if meta and meta.services:
                for sub_cls in meta.services:
                    self._register_entry_with_deps(sub_cls, registry)
        elif is_cf_service(cls):
            registry.register(cls, meta=get_service_meta(cls))  # type: ignore
        else:
            raise TypeError(
                f"Class '{cls.__name__}' is not decorated with @module or @service. "
                "Canary can only manage framework-decorated classes."
            )

        for dep_cls in resolve_deps(cls).values():
            self._register_entry_with_deps(dep_cls, registry)

    def _build_asgi_app(self) -> StarletteRouter:
        """Collect routes from all services and build the main Starlette router."""
        routes: list[Mount | Route] = []
        mount_paths: set[str] = set()
        root_routes: set[tuple[str, tuple[str, ...]]] = set()

        for name in self._startup_order:
            inst = self._registry.get_by_name(name).instance
            if inst is None:
                continue

            router = getattr(inst, "router", None)
            if not isinstance(router, _Router):
                continue

            # Check for custom mount path
            if hasattr(inst, "get_mount_path"):
                prefix = inst.get_mount_path()
            elif getattr(router, "prefix", "") != "":
                prefix = router.prefix
            else:
                prefix = "" if name == getattr(self._root_cls, "__name__", "") else f"/{name}"

            # Since _collect_routes needs to know if we are including prefix,
            # wait, _collect_routes bound methods.
            service_routes = _collect_routes(inst, include_router_prefix=False)
            if not service_routes:
                continue

            # If the prefix is empty string, we mount its routes at root
            if prefix == "":
                for route in service_routes:
                    methods = getattr(route, "methods", None)
                    method_key = tuple(sorted(methods)) if methods else ("MOUNT",)
                    route_key = (route.path, method_key)
                    if route_key in root_routes:
                        raise ValueError(
                            f"Route collision: '{route.path}' with methods {methods} is already in use."
                        )
                    routes.append(route)
                    root_routes.add(route_key)
            else:
                if prefix in mount_paths:
                    raise ValueError(f"Mount path collision: '{prefix}' is already in use.")
                routes.append(Mount(prefix, routes=service_routes))
                mount_paths.add(prefix)

        return StarletteRouter(routes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI Application Entry Point."""
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        else:
            if not self._doc_routes:
                async with self._openapi_lock:
                    if not self._doc_routes:
                        await self._generate_openapi()
                        # Mount doc routes dynamically since they are generated on first request
                        self._asgi_app.routes.extend(self._doc_routes)

            if self._asgi_app is not None:
                await self._asgi_app(scope, receive, send)
            else:
                response = PlainTextResponse("Not Found", status_code=404)
                await response(scope, receive, send)

    async def startup(self) -> None:
        """Start all services in topological order."""
        for name in self._startup_order:
            inst = self._registry.get_by_name(name).instance
            if hasattr(inst, "startup") and callable(inst.startup):
                _log.debug("Starting service: %s", type(inst).__name__)
                await inst.startup()

    async def shutdown(self) -> None:
        """Shut down all services in reverse topological order."""
        for name in reversed(self._startup_order):
            inst = self._registry.get_by_name(name).instance
            if hasattr(inst, "shutdown") and callable(inst.shutdown):
                _log.debug("Shutting down service: %s", type(inst).__name__)
                await inst.shutdown()

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        """Handle ASGI lifespan events for all services."""
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await self.startup()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                return
            else:
                _log.warning("Unknown lifespan message type: %s", message["type"])

    def _collect_route_defs_and_deps(self) -> list[tuple[Any, Any]]:
        """Collect all RouteDefs and EndpointMetas from all services for OpenAPI."""
        result = []
        for name in self._startup_order:
            inst = self._registry.get_by_name(name).instance
            if inst is None:
                continue

            router = getattr(inst, "router", None)
            if not isinstance(router, _Router):
                continue

            if hasattr(inst, "get_mount_path"):
                prefix = inst.get_mount_path()
            elif getattr(router, "prefix", "") != "":
                prefix = router.prefix
            else:
                prefix = "" if name == getattr(self._root_cls, "__name__", "") else f"/{name}"

            # If explicit empty prefix, use empty string for openapi generation path
            if prefix == "":
                prefix = ""

            for rdef in router._route_defs:
                meta = resolve_endpoint_meta(
                    path=prefix + rdef.path if rdef.path != "/" else prefix,
                    call=rdef.handler,
                    is_endpoint=True,
                    request_model=rdef.request_model,
                    http_method=rdef.method,
                )
                result.append((rdef, meta))
        return result

    async def _generate_openapi(self) -> None:
        """Generate OpenAPI schema and build doc routes."""
        route_defs_and_deps = self._collect_route_defs_and_deps()
        if not route_defs_and_deps:
            return

        def schema_factory() -> dict[str, object]:
            from canary_framework.core.web.openapi import generate_openapi_schema

            return generate_openapi_schema(
                route_defs_and_deps,
                title=self._config.openapi_title,
                version=self._config.openapi_version,
                description=self._config.openapi_description,
                servers=self._config.openapi_servers or None,
                security_schemes=self._config.openapi_security_schemes or None,
            )

        self._doc_routes = _build_doc_routes(
            schema_factory,
            openapi_path=self._config.docs_openapi_path,
            swagger_path=self._config.docs_swagger_path,
            redoc_path=self._config.docs_redoc_path,
            swagger_css=self._config.docs_swagger_css_cdn,
            swagger_js=self._config.docs_swagger_js_cdn,
            redoc_js=self._config.docs_redoc_cdn,
        )


__all__ = ["Canary"]
