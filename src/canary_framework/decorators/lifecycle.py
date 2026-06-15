"""生命周期钩子装饰器实现。

提供@before_startup、@before_shutdown装饰器。

Lifecycle hook decorators implementation.

Provides @after_init, @before_startup, @before_shutdown decorators.
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import CF_HOOK_MARKER_MAP, HookFunction, LifecycleHook


def _lifecycle_hook(phase: LifecycleHook) -> Callable[[HookFunction], HookFunction]:
    """创建生命周期钩子装饰器的工厂函数。

    Args:
        phase: 生命周期阶段。

    Returns:
        钩子装饰器。

    Factory function for creating lifecycle hook decorators.

    Args:
        phase: The lifecycle phase.

    Returns:
        Hook decorator.
    """

    def decorator(func: HookFunction) -> HookFunction:
        """装饰器，标记方法为生命周期钩子。

        Args:
            func: 要装饰的方法。

        Returns:
            装饰后的方法。

        Decorator that marks a method as a lifecycle hook.

        Args:
            func: The method to decorate.

        Returns:
            The decorated method.
        """
        setattr(func, CF_HOOK_MARKER_MAP[phase], True)
        return func

    return decorator


before_startup = _lifecycle_hook(LifecycleHook.BEFORE_STARTUP)
"""启动前执行的钩子装饰器。

在模块启动前调用。

Hook decorator executed before startup.

Called before the module starts.
"""

before_shutdown = _lifecycle_hook(LifecycleHook.BEFORE_SHUTDOWN)
"""关闭前执行的钩子装饰器。

在模块关闭前调用。

Hook decorator executed before shutdown.

Called before the module shuts down.
"""


__all__ = [
    "before_shutdown",
    "before_startup",
]
