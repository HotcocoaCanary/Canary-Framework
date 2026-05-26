"""Trace decorator — AOP method call logging.

设计思路 (Design rationale):
    ``@trace`` 是框架的 AOP（面向切面编程）机制。同时支持：
    - 类装饰器：注入 ``__getattribute__`` 代理，拦截所有公开方法调用
    - 方法装饰器：单方法包装
"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Any

from canary_framework.common._logging import get_logger

_log = get_logger("trace")

_MAX_RESULT_LEN = 200
"""出参截断阈值 (Maximum result string length before truncation)."""


def trace(target: type | Callable[..., Any]) -> type | Callable[..., Any]:
    """AOP call logging — intercepts method calls and logs args/results.

    双重装饰器：
    - 类装饰器：AOP 切面，拦截实例所有公开方法
    - 方法装饰器：只记录被装饰的单个方法

    Args:
        target: 一个类或可调用对象。A class or callable.

    Returns:
        被包装后的类或方法。The wrapped class or callable.

    Example (class-level AOP)::

        @trace
        @service(name="user_service")
        class UserService:
            async def create_user(self, name: str) -> User: ...

    Example (method-level)::

        class UserService:
            @trace
            async def create_user(self, name: str) -> User: ...
    """
    if isinstance(target, type):
        return _trace_class(target)
    return _trace_method(target)


def _trace_class(cls: type) -> type:
    """AOP proxy: intercept all public method calls via __getattribute__."""

    def traced_getattr(instance: object, attr_name: str) -> object:
        value = object.__getattribute__(instance, attr_name)
        if attr_name.startswith("_") or not callable(value):
            return value
        return _make_traced(value, qualname=f"{cls.__name__}.{attr_name}")

    cls.__getattribute__ = traced_getattr  # type: ignore[method-assign,assignment]
    return cls


def _trace_method(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a single method with call logging."""
    qualname = getattr(fn, "__qualname__", fn.__name__)
    return _make_traced(fn, qualname=qualname)


def _make_traced(fn: Callable[..., Any], qualname: str) -> Callable[..., Any]:
    """Create a traced wrapper that logs before/after/error."""

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        call_repr = _format_call(args, kwargs)
        _log.debug("%s ⇠ %s", qualname, call_repr)
        try:
            result = fn(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000
            result_repr = _format_result(result)
            _log.debug("%s ⇢ %s (%.0fms)", qualname, result_repr, elapsed)
            return result
        except Exception:
            elapsed = (time.monotonic() - start) * 1000
            _log.error("%s ✗ failed (%.0fms)", qualname, elapsed, exc_info=True)
            raise

    @functools.wraps(fn)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        call_repr = _format_call(args, kwargs)
        _log.debug("%s ⇠ %s", qualname, call_repr)
        try:
            result = await fn(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000
            result_repr = _format_result(result)
            _log.debug("%s ⇢ %s (%.0fms)", qualname, result_repr, elapsed)
            return result
        except Exception:
            elapsed = (time.monotonic() - start) * 1000
            _log.error("%s ✗ failed (%.0fms)", qualname, elapsed, exc_info=True)
            raise

    if inspect.iscoroutinefunction(fn):
        return async_wrapper
    return sync_wrapper


def _format_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Format call arguments for logging (skip *self*)."""
    parts: list[str] = []
    for a in args[1:]:  # 跳过 self
        parts.append(repr(a))
    for k, v in kwargs.items():
        parts.append(f"{k}={v!r}")
    return ", ".join(parts)


def _format_result(result: Any) -> str:
    """Format return value for logging — truncate if too long."""
    s = repr(result)
    if len(s) > _MAX_RESULT_LEN:
        s = s[:_MAX_RESULT_LEN] + "…"
    return s
