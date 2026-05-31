"""ServiceBase — lifecycle-aware service with hook invocation.

Provides configure / init / startup / shutdown lifecycle with
declarative hook support via ``@after_config``, ``@after_init``,
``@before_startup``, ``@before_shutdown``.
"""

from __future__ import annotations

import inspect

from canary_framework.common import LifecycleHook, LifecycleHookError
from canary_framework.engine.hooks import HookDict, find_hooks


class ServiceBase:
    """Auto-injected base for ``@service``-decorated classes.

    Provides configure / init / startup / shutdown lifecycle.
    """

    def __init__(self) -> None:
        self._cf_hooks: HookDict | None = None
        self.config: object = None
        super().__init__()

    async def configure(self, config_instance: object = None) -> None:
        self.config = config_instance
        await self._invoke_hook(LifecycleHook.AFTER_CONFIG)

    async def init(self) -> None:
        await self._invoke_hook(LifecycleHook.AFTER_INIT)

    async def startup(self) -> None:
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)

    async def shutdown(self) -> None:
        await self._invoke_hook(LifecycleHook.BEFORE_SHUTDOWN)

    async def _invoke_hook(self, hook: LifecycleHook) -> None:
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
