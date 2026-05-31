"""ModuleBase — orchestrates child services through lifecycle phases.

Handles instantiation, DI wiring, configure/init/startup/shutdown
in topological order, and exposes a starlette :class:`Router` for
ASGI mounting.
"""

from __future__ import annotations

from typing import cast

from starlette.routing import Mount
from starlette.routing import Router as StarletteRouter
from starlette.types import ASGIApp, Receive, Scope, Send

from canary_framework.common import (
    DependencyInjectionError,
    LifecycleHook,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)
from canary_framework.core.service import ServiceBase
from canary_framework.engine.hooks import LifecycleAware
from canary_framework.engine.injector import inject_deps, to_snake, topological_sort
from canary_framework.engine.registry import Registry


class ModuleBase(ServiceBase):
    """Auto-injected base for ``@module``-decorated classes.

    Orchestrates child service lifecycle — instantiation, DI wiring,
    configure/init/startup/shutdown in topological order.
    """

    def __init__(self) -> None:
        super().__init__()
        self._cf_parent_registry: Registry | None = None
        self._cf_registry: Registry | None = None
        self._cf_startup_order: list[str] = []
        self._cf_asgi_app: StarletteRouter | None = None

    async def configure(self, config_instance: object = None) -> None:
        self.config = config_instance

        meta = get_module_meta(type(self))
        if not meta.services:
            await self._invoke_hook(LifecycleHook.AFTER_CONFIG)
            return

        parent_registry = getattr(self, "_cf_parent_registry", None)
        registry = Registry(parent=parent_registry)
        self._cf_registry = registry

        for sub_cls in meta.services:
            self._register_entry_with_deps(sub_cls, registry)

        self._cf_startup_order = topological_sort(registry)

        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            entry.instance = entry.cls()

        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            inst = entry.instance
            if inst is None:
                raise DependencyInjectionError(
                    f"Service '{name}' instance is None during wiring."
                )
            inject_deps(inst, entry, registry)
            if isinstance(inst, ModuleBase):
                inst._cf_parent_registry = registry
            setattr(self, to_snake(entry.cls.__name__), inst)

        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            child = entry.instance
            if child is None:
                raise DependencyInjectionError(
                    f"Service '{name}' instance is None during configure."
                )
            await cast(LifecycleAware, child).configure(config_instance)

        await self._invoke_hook(LifecycleHook.AFTER_CONFIG)

    async def init(self) -> None:
        await self._invoke_hook(LifecycleHook.AFTER_INIT)
        registry = self._cf_registry
        if registry is not None:
            for name in self._cf_startup_order:
                child = registry.get_by_name(name).instance
                if child is None:
                    raise DependencyInjectionError(
                        f"Service '{name}' instance is None during init."
                    )
                await cast(LifecycleAware, child).init()

    @property
    def asgi_app(self) -> StarletteRouter:
        if self._cf_asgi_app is None:
            routes: list[Mount] = []
            registry = self._cf_registry
            if registry is not None:
                for name in self._cf_startup_order:
                    entry = registry.get_by_name(name)
                    inst = entry.instance
                    if inst is not None and hasattr(inst, "asgi_app"):
                        app = cast(ASGIApp, inst.asgi_app)
                        routes.append(Mount(f"/{name}", app=app))
            self._cf_asgi_app = StarletteRouter(routes)
        return self._cf_asgi_app

    async def startup(self) -> None:
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)
        registry = self._cf_registry
        if registry is not None:
            for name in self._cf_startup_order:
                child = registry.get_by_name(name).instance
                if child is None:
                    raise DependencyInjectionError(
                        f"Service '{name}' instance is None during startup."
                    )
                await cast(LifecycleAware, child).startup()

    async def shutdown(self) -> None:
        await self._invoke_hook(LifecycleHook.BEFORE_SHUTDOWN)
        registry = self._cf_registry
        if registry is not None:
            for name in reversed(self._cf_startup_order):
                child = registry.get_by_name(name).instance
                if child is None:
                    raise DependencyInjectionError(
                        f"Service '{name}' instance is None during shutdown."
                    )
                await cast(LifecycleAware, child).shutdown()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        else:
            await self.asgi_app(scope, receive, send)

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await self.startup()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                return

    def _register_entry_with_deps(self, cls: type, registry: Registry) -> None:
        if registry.has(cls):
            return
        parent = registry.parent
        if parent is not None and parent.has(cls):
            return

        if is_cf_module(cls):
            mod_meta = get_module_meta(cls)
            registry.register(cls, meta=mod_meta)
            for dep in mod_meta.deps:
                self._register_entry_with_deps(dep, registry)
            return

        if is_cf_service(cls):
            svc_meta = get_service_meta(cls)
            registry.register(cls, meta=svc_meta)
            for dep in svc_meta.deps:
                self._register_entry_with_deps(dep, registry)
            return

        raise TypeError(
            f"'{cls.__name__}' is not decorated with @service or @module."
        )


__all__ = ["ModuleBase"]
