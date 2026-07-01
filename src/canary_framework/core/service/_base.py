"""ServiceBase — 具有钩子调用功能的生命周期感知服务基类。

提供init/startup/shutdown生命周期方法，
支持通过@before_startup、@before_shutdown装饰器声明式地注册钩子。

ServiceBase — lifecycle-aware service with hook invocation.

Provides init / startup / shutdown lifecycle with
declarative hook support via @before_startup, @before_shutdown.
"""

from __future__ import annotations

import inspect
from types import FunctionType
from typing import NamedTuple, cast

from starlette.routing import Route
from starlette.routing import Router as StarletteRouter
from starlette.types import Receive, Scope, Send

from canary_framework.common import (
    LifecycleHook,
    LifecycleHookError,
    ResolvedRoute,
)
from canary_framework.common.config import CanaryConfig
from canary_framework.common.logging import get_logger
from canary_framework.core.router import Router, _build_doc_routes
from canary_framework.core.router._utils import _build_route, _check_route_collisions
from canary_framework.core.service._hooks import HookDict, find_hooks
from canary_framework.engine.openapi import generate_openapi_schema

_log = get_logger("service")


class Assembled(NamedTuple):
    """组装产物：路由表 + OpenAPI。Assembly product: router + openapi."""

    router: StarletteRouter
    openapi: dict[str, object]


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
        self._cf_assembled: Assembled | None = None
        super().__init__()

    def _get_router(self) -> Router | None:
        """获取服务的 Router 实例（如有）。

        Get the service's Router instance if one exists.
        """
        router = getattr(self, "router", None)
        return router if isinstance(router, Router) else None

    def _cf_collect_routes(self) -> list[ResolvedRoute]:
        """收集本服务的路由贡献：绑 self、拼 router.prefix。

        Collect this service's route contribution: bound to self,
        prefixed with router.prefix. Returns [] when no router.
        """
        router = self._get_router()
        if router is None:
            return []
        cls = type(self)
        out: list[ResolvedRoute] = []
        for info in router._route_infos:
            bound = cast(FunctionType, info.handler).__get__(self, cls)
            full_path = router.prefix + info.starlette_path
            while "//" in full_path:
                full_path = full_path.replace("//", "/")
            out.append(
                ResolvedRoute(
                    full_path=full_path,
                    handler=bound,
                    info=info,
                )
            )
        return out

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

        Start the service.

        Invokes the BEFORE_STARTUP hook.
        """
        _log.debug("Starting service: %s", type(self).__name__)
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)

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
            await self.asgi_app(scope, receive, send)

    @property
    def asgi_app(self) -> StarletteRouter:
        """获取 ASGI 应用（记忆化）。

        懒加载单点组装的 Starlette 路由器。

        Returns:
            StarletteRouter实例。

        Get the ASGI application (memoized).

        Lazily returns the single-point assembled Starlette router.

        Returns:
            StarletteRouter instance.
        """
        if self._cf_assembled is None:
            self._cf_assembled = self._cf_assemble()
        return self._cf_assembled.router

    def openapi(self) -> dict[str, object]:
        """返回本（子）树的 OpenAPI 文档（记忆化）。

        Return the OpenAPI document for this (sub)tree (memoized).
        """
        if self._cf_assembled is None:
            self._cf_assembled = self._cf_assemble()
        return self._cf_assembled.openapi

    def _cf_assemble(self) -> Assembled:
        """单点记忆化组装：收集 → 校验冲突 → 建路由表 + OpenAPI + 文档端点。

        Single-point assembly: collect → check collisions → build the routing
        table, OpenAPI document, and doc endpoints.
        """
        resolved = self._cf_collect_routes()
        if not resolved:
            return Assembled(StarletteRouter([]), {})
        _check_route_collisions(resolved)
        cfg = self.config or CanaryConfig()
        routes: list[Route] = [_build_route(r) for r in resolved]
        openapi = generate_openapi_schema(
            resolved,
            title=cfg.openapi_title,
            version=cfg.openapi_version,
            description=cfg.openapi_description,
            servers=cfg.openapi_servers or None,
            security_schemes=cfg.openapi_security_schemes or None,
        )
        routes += _build_doc_routes(
            openapi,
            openapi_path=cfg.docs_openapi_path,
            swagger_path=cfg.docs_swagger_path,
            redoc_path=cfg.docs_redoc_path,
            swagger_css=cfg.docs_swagger_css_cdn,
            swagger_js=cfg.docs_swagger_js_cdn,
            redoc_js=cfg.docs_redoc_cdn,
        )
        return Assembled(StarletteRouter(routes), openapi)

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


__all__ = ["Assembled", "ServiceBase"]
