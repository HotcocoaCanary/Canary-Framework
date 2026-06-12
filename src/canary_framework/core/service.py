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
from starlette.types import ASGIApp, Receive, Scope, Send

from canary_framework.common import (
    CF_NAME_ATTR,
    LifecycleHook,
    LifecycleHookError,
    get_service_meta,
)
from canary_framework.engine.hooks import HookDict, find_hooks
from canary_framework.engine.logging import get_logger

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

    async def init(self) -> None:
        """初始化服务。

        调用AFTER_INIT钩子。

        Initialize the service.

        Invokes the AFTER_INIT hook.
        """
        _log.debug("Initializing service: %s", type(self).__name__)
        await self._invoke_hook(LifecycleHook.AFTER_INIT)

    async def startup(self) -> None:
        """启动服务，可选地生成 OpenAPI schema 和文档端点。

        调用BEFORE_STARTUP钩子。
        如果该服务定义了路由（@get/@post等），则自动注册文档端点。

        Start the service, optionally generating OpenAPI schema and doc endpoints.

        Invokes the BEFORE_STARTUP hook.
        If the service defines routes (@get/@post etc.), auto-registers doc endpoints.
        """
        _log.debug("Starting service: %s", type(self).__name__)
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)
        await self._cf_setup_openapi()

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
            asgi = getattr(self, "asgi_app", None)
            if asgi is not None:
                await asgi(scope, receive, send)

    def get_mount_path(self) -> str:
        """返回服务在模块 ASGI 应用中的挂载路径。

        Returns the mount path for this service in the module's ASGI app.
        """
        meta = get_service_meta(type(self))
        if meta.prefix:
            return meta.prefix
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
    def asgi_app(self) -> ASGIApp | None:
        """获取ASGI应用。

        懒加载创建Starlette路由器，收集所有路由。
        独立运行时（无父Registry）自动包含文档端点。

        Returns:
            StarletteRouter实例或None。

        Get the ASGI application.

        Lazily creates the Starlette router and collects all routes.
        When running standalone (no parent registry), doc endpoints are included.

        Returns:
            StarletteRouter instance or None.
        """
        from canary_framework.core.router import _collect_routes

        if self._starlette_router is None:
            routes = _collect_routes(self)
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

    async def _cf_setup_openapi(self) -> None:
        """如果服务定义了路由，生成 OpenAPI schema 和文档端点。

        使用 first-wins 策略：沿 Registry 父子链向上查找 _cf_docs_registered，
        如果已注册则跳过。独立运行时（无父Registry）始终生成。

        Generate OpenAPI schema and doc endpoints when the service defines routes.
        Uses first-wins: walks the registry parent chain for _cf_docs_registered.
        Always generates when running standalone (no parent registry).
        """
        from canary_framework.common.config import CanaryConfig
        from canary_framework.core.router import (
            _REDOC_HTML,
            _SWAGGER_UI_HTML,
            _collect_routes,
        )
        from canary_framework.engine.openapi import generate_openapi_schema

        routes = _collect_routes(self)
        if not routes:
            return

        parent = self._cf_parent_registry
        walk: object | None = parent
        while walk is not None:
            if hasattr(walk, "_cf_docs_registered") and walk._cf_docs_registered:
                return
            walk = getattr(walk, "parent", None)

        meta = get_service_meta(type(self))
        router_metas: list[ServiceMeta] = [meta]
        if parent is not None and hasattr(parent, "all_entries"):
            from canary_framework.common import ServiceMeta, get_router_meta

            for entry in parent.all_entries():
                other_meta = get_router_meta(entry.cls)
                if other_meta is not None and other_meta is not meta:
                    router_metas.append(other_meta)

        config = next(
            (
                getattr(self, a)
                for a in dir(self)
                if isinstance(getattr(self, a, None), CanaryConfig)
            ),
            None,
        )
        cfg: CanaryConfig = config if isinstance(config, CanaryConfig) else CanaryConfig()
        schema = generate_openapi_schema(
            router_metas,
            title=cfg.openapi_title,
            version=cfg.openapi_version,
            description=cfg.openapi_description,
            servers=cfg.openapi_servers or None,
            security_schemes=cfg.openapi_security_schemes or None,
        )

        openapi_path = cfg.docs_openapi_path
        docs_path = cfg.docs_swagger_path
        redoc_path = cfg.docs_redoc_path

        swagger_css = cfg.docs_swagger_css_cdn
        swagger_js = cfg.docs_swagger_js_cdn
        redoc_js = cfg.docs_redoc_cdn

        swagger_html = (
            _SWAGGER_UI_HTML.replace(
                "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
                swagger_css,
            )
            .replace(
                "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
                swagger_js,
            )
            .replace(
                '"/openapi.json"',
                f'"{openapi_path}"',
            )
        )
        redoc_html = _REDOC_HTML.replace(
            "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            redoc_js,
        ).replace(
            '"/openapi.json"',
            f'"{openapi_path}"',
        )

        from starlette.responses import HTMLResponse, JSONResponse

        async def openapi_endpoint(_request: object) -> JSONResponse:
            return JSONResponse(schema)

        async def swagger_endpoint(_request: object) -> HTMLResponse:
            return HTMLResponse(swagger_html)

        async def redoc_endpoint(_request: object) -> HTMLResponse:
            return HTMLResponse(redoc_html)

        self._cf_root_routes = [
            Route(openapi_path, endpoint=openapi_endpoint, methods=["GET"]),
            Route(docs_path, endpoint=swagger_endpoint, methods=["GET"]),
            Route(redoc_path, endpoint=redoc_endpoint, methods=["GET"]),
        ]

        if parent is not None and hasattr(parent, "_cf_docs_registered"):
            parent._cf_docs_registered = True


__all__ = ["ServiceBase"]
