"""ServiceBase — 具有钩子调用功能的生命周期感知服务基类。

提供init/startup/shutdown生命周期方法，
支持通过@after_init、@before_startup、@before_shutdown装饰器声明式地注册钩子。

ServiceBase — lifecycle-aware service with hook invocation.

Provides init / startup / shutdown lifecycle with
declarative hook support via @after_init,
@before_startup, @before_shutdown.
"""

from __future__ import annotations

import inspect

from starlette.routing import Route
from starlette.routing import Router as StarletteRouter
from starlette.types import Receive, Scope, Send

from canary_framework.common import (
    CF_NAME_ATTR,
    LifecycleHook,
    LifecycleHookError,
    RouteInfo,
)
from canary_framework.common.config import CanaryConfig
from canary_framework.common.logging import get_logger
from canary_framework.core.service._hooks import HookDict, find_hooks

_log = get_logger("service")


class ServiceBase:
    """@service装饰类的自动注入基类。

    提供init/startup/shutdown生命周期方法。

    Auto-injected base for @service-decorated classes.

    Provides init / startup / shutdown lifecycle.
    """

    def __init__(self) -> None:
        """初始化ServiceBase实例。

        Initializes the ServiceBase instance.
        """
        self._cf_hooks: HookDict | None = None
        self._cf_parent_registry: object | None = None
        self._starlette_router: StarletteRouter | None = None
        self._cf_root_routes: list[Route] | None = None
        super().__init__()

    @property
    def config(self) -> CanaryConfig | None:
        """获取模块的配置对象。

        由父模块在初始化时自动传播，无需通过 DI 注入。

        Returns:
            配置实例，如果模块未声明 config 则返回 None。

        Get the module's config object.

        Propagated automatically by the parent module during init,
        no DI injection needed.

        Returns:
            The config instance, or None if no config is declared.
        """
        return getattr(self, "_cf_config", None)

    def init(self) -> None:
        """初始化服务。

        Initialize the service.
        """
        _log.debug("Initializing service: %s", type(self).__name__)

    async def startup(self) -> None:
        """启动服务。

        调用BEFORE_STARTUP钩子。
        如果是顶层服务/模块（无父Registry），自动生成 OpenAPI 文档端点。

        Start the service.

        Invokes the BEFORE_STARTUP hook.
        Generates OpenAPI doc endpoints when running as top-level (no parent registry).
        """
        _log.debug("Starting service: %s", type(self).__name__)
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)
        if self._cf_parent_registry is None:
            await self._cf_generate_openapi()

    async def shutdown(self) -> None:
        """关闭服务。

        调用BEFORE_SHUTDOWN钩子。

        Shutdown the service.

        Invokes the BEFORE_SHUTDOWN hook.
        """
        _log.debug("Shutting down service: %s", type(self).__name__)
        await self._invoke_hook(LifecycleHook.BEFORE_SHUTDOWN)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI 应用入口点。

        处理 lifespan 协议映射到 startup/shutdown，
        其他请求委托给 asgi_app（如果存在）。

        ASGI application entry point.

        Handles lifespan protocol mapped to startup/shutdown,
        delegates other requests to asgi_app if available.
        """
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        else:
            if self._cf_parent_registry is None and self._cf_root_routes is None:
                await self._cf_generate_openapi()
            asgi = self.asgi_app
            if asgi is not None:
                await asgi(scope, receive, send)
            else:
                from starlette.responses import PlainTextResponse

                response = PlainTextResponse("Not Found", status_code=404)
                await response(scope, receive, send)

    def get_mount_path(self) -> str:
        """返回服务在模块 ASGI 应用中的挂载路径。"""
        from canary_framework.core.router import Router

        router = getattr(self, "router", None)
        if isinstance(router, Router) and router.prefix:
            return router.prefix
        return f"/{getattr(type(self), CF_NAME_ATTR, type(self).__name__)}"

    def _cf_get_root_routes(self) -> list[Route]:
        """返回需要在模块根路径注册的路由（如文档端点）。

        仅在 Module 中运行时有效，独立运行时返回空列表。

        Return root-level routes (e.g., doc endpoints) for the parent module.
        """
        if self._cf_parent_registry is not None and self._cf_root_routes:
            return self._cf_root_routes
        return []

    @property
    def asgi_app(self) -> StarletteRouter:
        """获取ASGI应用。

        懒加载创建Starlette路由器，收集所有路由。
        独立运行时（无父Registry）自动包含文档端点。

        Returns:
            StarletteRouter实例。

        Get the ASGI application.

        Lazily creates the Starlette router and collects all routes.
        When running standalone (no parent registry), doc endpoints are included.

        Returns:
            StarletteRouter instance.
        """
        from canary_framework.core.router import _collect_routes

        if self._starlette_router is None:
            include_prefix = self._cf_parent_registry is None
            routes = _collect_routes(self, include_router_prefix=include_prefix)
            if self._cf_root_routes and self._cf_parent_registry is None:
                routes.extend(self._cf_root_routes)
            _log.debug("Collected %d route(s) for service: %s", len(routes), type(self).__name__)
            for route in routes:
                _log.debug("  Route: %s %s", route.methods, route.path)
            self._starlette_router = StarletteRouter(routes)
        return self._starlette_router

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        """处理 ASGI lifespan 协议。

        startup → self.startup()
        shutdown → self.shutdown()

        Handle ASGI lifespan protocol.
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
            else:
                _log.warning("Unknown lifespan message type: %s", message["type"])

    async def _invoke_hook(self, hook: LifecycleHook) -> None:
        """调用指定的生命周期钩子。

        如果钩子函数不存在则跳过。
        如果钩子是协程函数则await执行，否则直接调用。
        如果钩子抛出异常，将其包装为LifecycleHookError。

        Args:
            hook: 要调用的生命周期钩子类型。

        Raises:
            LifecycleHookError: 如果钩子执行时抛出异常。

        Invoke the specified lifecycle hook.

        Skips if the hook function doesn't exist.
        Awaits if the hook is a coroutine function, otherwise calls directly.
        Wraps any exceptions raised by the hook in LifecycleHookError.

        Args:
            hook: The lifecycle hook type to invoke.

        Raises:
            LifecycleHookError: If the hook raises an exception during execution.
        """
        if self._cf_hooks is None:
            self._cf_hooks = find_hooks(self)
        fn = self._cf_hooks.get(hook)
        if fn is None:
            return
        try:
            if inspect.iscoroutinefunction(fn):
                await fn()
            else:
                _ = fn()
        except Exception as exc:
            raise LifecycleHookError(
                f"Service raised an error in {hook.value} hook: {exc}"
            ) from exc

    def _cf_collect_route_infos(self) -> list[RouteInfo]:
        """收集自身及子服务的所有 RouteInfo。"""
        from canary_framework.core.router import Router

        route_infos: list[RouteInfo] = []
        router = getattr(self, "router", None)
        if isinstance(router, Router):
            route_infos.extend(router._route_infos)

        registry = getattr(self, "_cf_registry", None)
        if registry is not None:
            for name in getattr(self, "_cf_startup_order", []):
                entry = registry.get_by_name(name)
                inst = entry.instance
                if inst is not None and hasattr(inst, "_cf_collect_route_infos"):
                    route_infos.extend(inst._cf_collect_route_infos())
        return route_infos

    async def _cf_generate_openapi(self) -> None:
        """收集全部路由，生成 OpenAPI schema 和文档端点。"""
        from canary_framework.core.router import _build_doc_routes
        from canary_framework.engine.openapi import generate_openapi_schema

        route_infos = self._cf_collect_route_infos()
        if not route_infos:
            return

        cfg = self.config or CanaryConfig()
        schema = generate_openapi_schema(
            route_infos,
            title=cfg.openapi_title,
            version=cfg.openapi_version,
            description=cfg.openapi_description,
            servers=cfg.openapi_servers or None,
            security_schemes=cfg.openapi_security_schemes or None,
        )

        self._cf_root_routes = _build_doc_routes(
            schema,
            openapi_path=cfg.docs_openapi_path,
            swagger_path=cfg.docs_swagger_path,
            redoc_path=cfg.docs_redoc_path,
            swagger_css=cfg.docs_swagger_css_cdn,
            swagger_js=cfg.docs_swagger_js_cdn,
            redoc_js=cfg.docs_redoc_cdn,
        )


__all__ = ["ServiceBase"]
