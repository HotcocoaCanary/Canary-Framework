"""生命周期钩子发现工具。

提供find_hooks函数用于查找服务实例的生命周期钩子。

Lifecycle hook discovery utilities.

Provides find_hooks function for discovering lifecycle hooks on service instances.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook

HookDict = dict[LifecycleHook, Callable[..., object] | None]
"""生命周期钩子字典类型。

Type alias for lifecycle hook dictionary.
"""


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
        LifecycleHook.AFTER_INIT: None,
        LifecycleHook.BEFORE_STARTUP: None,
        LifecycleHook.BEFORE_SHUTDOWN: None,
    }
    child_cls = type(instance)
    hook_methods: dict[LifecycleHook, object] = {}
    for cls in reversed(child_cls.__mro__):
        for _name, attr_obj in cls.__dict__.items():
            for hook, marker in CF_HOOK_MARKER_MAP.items():
                if getattr(attr_obj, marker, False):
                    hook_methods[hook] = attr_obj

    for hook, attr_obj in hook_methods.items():
        hooks[hook] = cast(Any, attr_obj).__get__(instance, child_cls)
    return hooks


__all__ = ["HookDict", "find_hooks"]
