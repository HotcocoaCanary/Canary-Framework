"""ServiceBase — 具有钩子调用功能的生命周期感知服务基类。

提供configure/init/startup/shutdown生命周期方法，
支持通过@after_config、@after_init、@before_startup、@before_shutdown装饰器声明式地注册钩子。

ServiceBase — lifecycle-aware service with hook invocation.

Provides configure / init / startup / shutdown lifecycle with
declarative hook support via @after_config, @after_init,
@before_startup, @before_shutdown.
"""

from __future__ import annotations

import inspect

from canary_framework.common import LifecycleHook, LifecycleHookError
from canary_framework.engine.hooks import HookDict, find_hooks


class ServiceBase:
    """@service装饰类的自动注入基类。

    提供configure/init/startup/shutdown生命周期方法。

    Auto-injected base for @service-decorated classes.

    Provides configure / init / startup / shutdown lifecycle.
    """

    def __init__(self) -> None:
        """初始化ServiceBase实例。

        Initializes the ServiceBase instance.
        """
        self._cf_hooks: HookDict | None = None
        self.config: object = None
        super().__init__()

    async def configure(self, config_instance: object = None) -> None:
        """配置服务。

        设置配置实例并调用AFTER_CONFIG钩子。

        Args:
            config_instance: 配置对象实例。

        Configure the service.

        Sets the config instance and invokes the AFTER_CONFIG hook.

        Args:
            config_instance: The configuration object instance.
        """
        self.config = config_instance
        await self._invoke_hook(LifecycleHook.AFTER_CONFIG)

    async def init(self) -> None:
        """初始化服务。

        调用AFTER_INIT钩子。

        Initialize the service.

        Invokes the AFTER_INIT hook.
        """
        await self._invoke_hook(LifecycleHook.AFTER_INIT)

    async def startup(self) -> None:
        """启动服务。

        调用BEFORE_STARTUP钩子。

        Start the service.

        Invokes the BEFORE_STARTUP hook.
        """
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)

    async def shutdown(self) -> None:
        """关闭服务。

        调用BEFORE_SHUTDOWN钩子。

        Shutdown the service.

        Invokes the BEFORE_SHUTDOWN hook.
        """
        await self._invoke_hook(LifecycleHook.BEFORE_SHUTDOWN)

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
