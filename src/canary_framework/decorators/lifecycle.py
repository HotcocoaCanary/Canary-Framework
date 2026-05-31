"""Lifecycle hook decorators.

Usage::

    from canary_framework import after_config, after_init
    from canary_framework import before_startup, before_shutdown
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook


def after_config[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``after_config`` lifecycle hook."""
    setattr(fn, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)
    return fn


def after_init[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``after_init`` lifecycle hook."""
    setattr(fn, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_INIT], True)
    return fn


def before_startup[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``before_startup`` lifecycle hook."""
    setattr(fn, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_STARTUP], True)
    return fn


def before_shutdown[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``before_shutdown`` lifecycle hook."""
    setattr(fn, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_SHUTDOWN], True)
    return fn


__all__ = [
    "after_config",
    "after_init",
    "before_shutdown",
    "before_startup",
]
