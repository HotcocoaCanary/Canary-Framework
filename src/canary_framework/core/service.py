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

from starlette.types import Receive, Scope, Send

from canary_framework.common import LifecycleHook, LifecycleHookError
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
            asgi = getattr(self, "asgi_app", None)
            if asgi is not None:
                await asgi(scope, receive, send)

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


__all__ = ["ServiceBase"]
