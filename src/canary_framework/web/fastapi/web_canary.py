"""Web engine — extends :class:`Canary` for FastAPI + Uvicorn integration.

:class:`WebCanary` inherits from :class:`~canary_framework.core.engine.canary.Canary`
and overrides :meth:`start` to boot a combined FastAPI / Uvicorn server.

Configuration prefix convention (root module's ``@config`` class):

    =================  ===========================  =========================
    Prefix             Consumer                     Example field
    =================  ===========================  =========================
    ``uvicorn_*``      ``uvicorn.Config``           ``uvicorn_host``
    ``fastapi_*``      ``FastAPI()``                ``fastapi_title``
    (no prefix)        Business config (untouched)  ``database_url``
    =================  ===========================  =========================

The framework's own lifecycle hooks (``on_start``, ``on_end``) are
bound to the FastAPI lifespan, so they run when the server starts
and shuts down.

.. important::

    ``WebCanary`` requires the ``[web]`` optional dependency group
    (``pip install canary-framework[web]``).  Calling :meth:`start`
    without ``fastapi`` and ``uvicorn`` installed raises an
    :exc:`ImportError` with a clear upgrade instruction.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

from canary_framework.core.decorators.module import is_cf_module
from canary_framework.core.decorators.service import is_cf_service
from canary_framework.core.engine.canary import Canary
from canary_framework.core.registry.registry import Registry
from canary_framework.web.fastapi.decorators.router import (
    get_route_info,
    get_router_prefix,
    is_route_method,
)
from canary_framework.web.fastapi.decorators.web import get_web_routers, is_web

_UVICORN_PREFIX = "uvicorn_"
_FASTAPI_PREFIX = "fastapi_"

_log = logging.getLogger("cf.web")


class WebCanary(Canary):
    """Canary variant that boots a FastAPI application via Uvicorn.

    Usage::

        @config
        class AppConfig:
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 8000
            fastapi_title: str = "My API"

        @web()
        @module(name="AppModule", config=AppConfig, services=[...])
        class AppModule:
            @get("/health")
            async def health(self) -> dict:
                return {"status": "ok"}

        app = WebCanary(AppModule)
        await app.init()
        await app.start()  # blocks until server stops
    """

    async def start(self) -> None:
        """Start the FastAPI + Uvicorn server.

        Steps:
            1. Extract ``uvicorn_*`` and ``fastapi_*`` fields from the
               root module's config.
            2. Build a FastAPI lifespan that calls the framework's
               ``on_start`` / ``on_end`` hooks.
            3. Register all ``@web``-annotated route methods.
            4. Launch ``uvicorn.Server.serve()``.

        Raises:
            ImportError: If ``fastapi`` or ``uvicorn`` are not installed.
                Install with ``pip install canary-framework[web]``.
        """
        try:
            from fastapi import FastAPI
        except ImportError:
            raise ImportError(
                "WebCanary requires FastAPI. Install it with: pip install canary-framework[web]"
            ) from None
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "WebCanary requires Uvicorn. Install it with: pip install canary-framework[web]"
            ) from None

        root_entry = self.registry.get_by_class(self._target)
        root_config = root_entry.config_instance

        uvicorn_kwargs: dict[str, Any] = {}
        fastapi_kwargs: dict[str, Any] = {}

        if root_config is not None:
            for key, value in vars(root_config).items():
                if key.startswith("_"):
                    continue
                if key.startswith(_UVICORN_PREFIX):
                    uvicorn_kwargs[key[len(_UVICORN_PREFIX) :]] = value
                elif key.startswith(_FASTAPI_PREFIX):
                    fastapi_kwargs[key[len(_FASTAPI_PREFIX) :]] = value

        # Safe defaults: bind to localhost by default
        host: str = uvicorn_kwargs.pop("host", "127.0.0.1")
        port: int = uvicorn_kwargs.pop("port", 8000)

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            """FastAPI lifespan: start framework services, register routes, stop."""
            await Canary.start(self)
            app.state.cf_registry = self.registry
            _register_routes(app, self.registry)
            _log.info("FastAPI ready — listening on %s:%d", host, port)
            yield
            _log.info("Shutting down…")
            await self.stop()

        fastapi_app = FastAPI(lifespan=lifespan, **fastapi_kwargs)

        config = uvicorn.Config(fastapi_app, host=host, port=port, **uvicorn_kwargs)
        server = uvicorn.Server(config)
        await server.serve()


# ---------------------------------------------------------------------------
# Internal route registration
# ---------------------------------------------------------------------------


def _register_routes(app: FastAPI, registry: Registry) -> None:
    """Scan all ``@web``-marked entries and register their HTTP routes.

    Three scenarios:
        1. External ``@router`` classes in ``routers=[]``.
        2. Route methods defined directly on the ``@web`` class (no routers).
        3. Combination of both (module with routers + own methods).
    """
    for entry in registry.all_entries():
        cls = entry.cls
        if not is_web(cls):
            continue

        routers = get_web_routers(cls)

        # External router classes
        for router_cls in routers:
            prefix = get_router_prefix(router_cls)
            ctx = entry.context
            if ctx is None:
                _log.warning(
                    "Context is None for '%s' — skipping router '%s'",
                    entry.name,
                    router_cls.__name__,
                )
                continue
            router_instance = router_cls(ctx)
            _register_instance_routes(app, router_instance, prefix)

        # Own methods (no external routers, or module with extra methods)
        owns_routers = bool(routers)
        is_container = is_cf_module(cls) or is_cf_service(cls)

        if not owns_routers and is_container:
            _register_instance_routes(app, entry.instance, "")

        if owns_routers and is_cf_module(cls):
            _register_instance_routes(app, entry.instance, "")


def _register_instance_routes(
    app: FastAPI,
    instance: object,
    prefix: str,
) -> None:
    """Scan *instance* for ``@get`` / ``@post`` / … methods and register them.

    Args:
        app: The FastAPI application instance.
        instance: An object whose class may contain route-decorated methods.
        prefix: URL prefix prepended to each method's path.
    """
    for _, method in inspect.getmembers(instance.__class__, inspect.isfunction):
        if not is_route_method(method):
            continue

        http_method, path, kwargs = get_route_info(method)
        full_path = prefix.rstrip("/") + "/" + path.lstrip("/")
        if full_path.endswith("/") and full_path != "/":
            full_path = full_path.rstrip("/")

        bound = getattr(instance, method.__name__)
        app.add_api_route(
            path=full_path,
            endpoint=bound,
            methods=[http_method],
            **kwargs,
        )
