"""ModuleBase — 通过生命周期阶段协调子服务的模块基类。

处理实例化、依赖注入、按拓扑顺序执行configure/init/startup/shutdown，
并暴露Starlette Router用于ASGI挂载。

ModuleBase — orchestrates child services through lifecycle phases.

Handles instantiation, DI wiring, configure/init/startup/shutdown
in topological order, and exposes a starlette Router for ASGI mounting.
"""

from __future__ import annotations

from typing import cast, override

from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.routing import Router as StarletteRouter
from starlette.types import ASGIApp, Receive, Scope, Send

from canary_framework.common import (
    DependencyInjectionError,
    LifecycleHook,
    RouterMeta,
    get_module_meta,
    get_router_meta,
    get_service_meta,
    is_cf_module,
    is_cf_router,
    is_cf_service,
)
from canary_framework.core.service import ServiceBase
from canary_framework.engine.hooks import LifecycleAware
from canary_framework.engine.injector import inject_deps, to_snake, topological_sort
from canary_framework.engine.logging import ensure_logging, get_logger
from canary_framework.engine.openapi import generate_openapi_schema
from canary_framework.engine.registry import Registry

_log = get_logger("module")

_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" });
    </script>
</body>
</html>"""

_REDOC_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>ReDoc</title>
</head>
<body>
    <div id="redoc"></div>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
    <script>
        Redoc.init("/openapi.json", {}, document.getElementById("redoc"));
    </script>
</body>
</html>"""


class ModuleBase(ServiceBase):
    """@module装饰类的自动注入基类。

    协调子服务生命周期——实例化、依赖注入、按拓扑顺序执行
    configure/init/startup/shutdown。

    Auto-injected base for @module-decorated classes.

    Orchestrates child service lifecycle — instantiation, DI wiring,
    configure/init/startup/shutdown in topological order.
    """

    def __init__(self) -> None:
        """初始化ModuleBase实例。

        Initializes the ModuleBase instance.
        """
        super().__init__()
        self._cf_parent_registry: Registry | None = None
        self._cf_registry: Registry | None = None
        self._cf_startup_order: list[str] = []
        self._cf_asgi_app: StarletteRouter | None = None
        self.config: object = None

    @override
    async def configure(self, config_instance: object = None) -> None:
        """配置模块及其所有子服务。

        设置配置实例，创建注册表，注册所有服务及其依赖，
        执行拓扑排序，实例化服务，注入依赖，然后调用每个服务的configure方法。

        Args:
            config_instance: 配置对象实例。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Configure the module and all its child services.

        Sets the config instance, creates registry, registers all services and
        their dependencies, performs topological sort, instantiates services,
        injects dependencies, and calls configure on each service.

        Args:
            config_instance: The configuration object instance.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        _log.info("Configuring module: %s", type(self).__name__)
        self.config = config_instance

        cf_log_level = getattr(config_instance, "cf_log_level", "INFO")
        ensure_logging(cf_log_level)

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
                raise DependencyInjectionError(f"Service '{name}' instance is None during wiring.")
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

    @override
    async def init(self) -> None:
        """初始化模块及其所有子服务。

        调用AFTER_INIT钩子，然后按拓扑顺序调用每个子服务的init方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Initialize the module and all its child services.

        Invokes the AFTER_INIT hook, then calls init on each child service
        in topological order.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        _log.info("Initializing module: %s", type(self).__name__)
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
        """获取ASGI应用。

        懒加载创建Starlette路由器，挂载所有具有asgi_app属性的子服务，
        以及Swagger UI、ReDoc和OpenAPI JSON文档端点。

        Returns:
            StarletteRouter实例，包含所有子路由器的挂载点和文档端点。

        Get the ASGI application.

        Lazily creates the Starlette router with mounts for all child services
        that have an asgi_app attribute, plus Swagger UI, ReDoc, and OpenAPI
        JSON documentation endpoints.

        Returns:
            StarletteRouter instance with mounts for child routers and docs.
        """
        if self._cf_asgi_app is None:
            routes: list[Route | Mount] = []
            registry = self._cf_registry
            if registry is not None:
                for name in self._cf_startup_order:
                    entry = registry.get_by_name(name)
                    inst = entry.instance
                    asgi = getattr(inst, "asgi_app", None)
                    if asgi is not None:
                        app = cast(ASGIApp, asgi)
                        routes.append(Mount(f"/{name}", app=app))

            router_metas: list[RouterMeta] = []
            if registry is not None:
                for name in self._cf_startup_order:
                    entry = registry.get_by_name(name)
                    if is_cf_router(entry.cls):
                        meta = get_router_meta(entry.cls)
                        if meta is not None:
                            router_metas.append(meta)

            openapi_schema = generate_openapi_schema(router_metas)

            async def openapi_endpoint(_request: object) -> JSONResponse:
                return JSONResponse(openapi_schema)

            async def swagger_endpoint(_request: object) -> HTMLResponse:
                return HTMLResponse(_SWAGGER_UI_HTML)

            async def redoc_endpoint(_request: object) -> HTMLResponse:
                return HTMLResponse(_REDOC_HTML)

            routes.append(Route("/openapi.json", endpoint=openapi_endpoint, methods=["GET"]))
            routes.append(Route("/docs", endpoint=swagger_endpoint, methods=["GET"]))
            routes.append(Route("/redoc", endpoint=redoc_endpoint, methods=["GET"]))

            self._cf_asgi_app = StarletteRouter(routes)
        assert self._cf_asgi_app is not None
        return self._cf_asgi_app

    @override
    async def startup(self) -> None:
        """启动模块及其所有子服务。

        调用BEFORE_STARTUP钩子，然后按拓扑顺序调用每个子服务的startup方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Start the module and all its child services.

        Invokes the BEFORE_STARTUP hook, then calls startup on each child service
        in topological order.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        _log.info("Starting module: %s", type(self).__name__)
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

    @override
    async def shutdown(self) -> None:
        """关闭模块及其所有子服务。

        调用BEFORE_SHUTDOWN钩子，然后按逆拓扑顺序调用每个子服务的shutdown方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Shutdown the module and all its child services.

        Invokes the BEFORE_SHUTDOWN hook, then calls shutdown on each child service
        in reverse topological order.

        Raises:
            DependencyInjectionError: 如果服务实例为None。
        """
        _log.info("Shutting down module: %s", type(self).__name__)
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
        """ASGI应用入口点。

        如果是生命周期请求，则处理startup/shutdown；否则委托给asgi_app。

        Args:
            scope: ASGI scope字典。
            receive: 接收消息的异步函数。
            send: 发送消息的异步函数。

        ASGI application entry point.

        Handles startup/shutdown for lifecycle requests, otherwise delegates
        to the asgi_app.

        Args:
            scope: ASGI scope dictionary.
            receive: Async function to receive messages.
            send: Async function to send messages.
        """
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        else:
            await self.asgi_app(scope, receive, send)

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        """处理ASGI生命周期协议。

        监听startup和shutdown消息，并调用相应的方法。

        Args:
            receive: 接收消息的异步函数。
            send: 发送消息的异步函数。

        Handle ASGI lifespan protocol.

        Listens for startup and shutdown messages and calls the appropriate methods.

        Args:
            receive: Async function to receive messages.
            send: Async function to send messages.
        """
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
        """递归注册服务及其依赖。

        如果服务/模块已在当前或父注册表中注册，则跳过。
        否则注册它并递归注册其依赖。

        Args:
            cls: 要注册的类。
            registry: 目标注册表。

        Raises:
            TypeError: 如果类没有被@service或@module装饰。

        Recursively register a service and its dependencies.

        Skips if the service/module is already registered in current or parent registry.
        Otherwise registers it and recursively registers its dependencies.

        Args:
            cls: The class to register.
            registry: The target registry.

        Raises:
            TypeError: If the class is not decorated with @service or @module.
        """
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

        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")


__all__ = ["ModuleBase"]
