"""生命周期钩子发现工具。

提供find_hooks函数用于查找服务实例的生命周期钩子。

Lifecycle hook discovery utilities.

Provides find_hooks function for discovering lifecycle hooks on service instances.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook

HookDict = dict[LifecycleHook, Callable[..., object] | None]
"""生命周期钩子字典类型。

Type alias for lifecycle hook dictionary.
"""


class LifecycleAware(Protocol):
    """生命周期感知接口。

    定义服务和模块必须实现的生命周期方法。

    Lifecycle-aware interface.

    Defines lifecycle methods that services and modules must implement.
    """

    async def configure(self, config_instance: object = None) -> None: ...
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...


def find_hooks(instance: object) -> HookDict:
    """查找实例上的所有生命周期钩子。

    遍历类继承链，查找带有生命周期钩子标记的方法。

    Args:
        instance: 要查找钩子的服务实例。

    Returns:
        包含所有生命周期钩子的字典，值为钩子函数或None。

    Find all lifecycle hooks on an instance.

    Traverses the class inheritance chain to find methods with lifecycle hook markers.

    Args:
        instance: The service instance to search for hooks.

    Returns:
        Dictionary containing all lifecycle hooks with hook functions or None.
    """
    hooks: HookDict = {
        LifecycleHook.AFTER_CONFIG: None,
        LifecycleHook.AFTER_INIT: None,
        LifecycleHook.BEFORE_STARTUP: None,
        LifecycleHook.BEFORE_SHUTDOWN: None,
    }
    for cls in type(instance).__mro__:
        for _name, attr_obj in cls.__dict__.items():
            if not callable(attr_obj):
                continue
            for hook, marker in CF_HOOK_MARKER_MAP.items():
                if getattr(attr_obj, marker, False) and hooks[hook] is None:
                    hooks[hook] = attr_obj.__get__(instance, cls)
                    break
        if all(v is not None for v in hooks.values()):
            break
    return hooks


__all__ = ["HookDict", "LifecycleAware", "find_hooks"]
