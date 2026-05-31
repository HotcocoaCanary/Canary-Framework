"""Lifecycle-aware protocol and hook discovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook

HookDict = dict[LifecycleHook, Callable[..., object] | None]


class LifecycleAware(Protocol):
    async def configure(self, config_instance: object = None) -> None: ...
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...


def find_hooks(instance: object) -> HookDict:
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
