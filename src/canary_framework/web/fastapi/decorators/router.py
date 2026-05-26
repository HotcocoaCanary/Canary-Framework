"""HTTP method decorators — ``@router``, ``@get``, ``@post``, ``@put``, ``@delete``, ``@patch``.

设计思路 (Design rationale):
    为什么不用 FastAPI 原生的 ``APIRouter``？
    （Why not use FastAPI's native ``APIRouter``?）

    原生 ``APIRouter`` 需要在模块级别实例化，无法接收框架的 ``Context``。
    框架的路由类在 ``__init__(self, ctx)`` 中接收 Context，使得路由方法
    可以访问 ``ctx.resolve(DBService)`` 和 ``ctx.get_config(AppConfig)``。
    这是框架统一 Context 设计的自然延伸。

    装饰器工厂模式 (Decorator factory pattern):
        ``_make_route(method)`` 避免为每个 HTTP 方法手写几乎相同的代码。
        5 行工厂函数替代 5 个 15 行的装饰器定义。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_RT_ATTR = "__cf_router__"
"""Set to ``True`` on classes decorated with ``@router``."""

_RT_PREFIX = "__cf_router_prefix__"
"""Stores the URL prefix string from ``@router(prefix=...)``."""

_RT_ROUTE = "__cf_route__"
"""Set to ``True`` on methods decorated with ``@get`` / ``@post`` / …."""


# ============================================================================
# @router
# ============================================================================


def router(
    prefix: str = "",
    deps: list[type] | None = None,
) -> Callable[[type], type]:
    """Mark a class as a route handler with an optional URL prefix.

    将类声明为路由类，其所有 HTTP 方法路径加上前缀。

    Args:
        prefix: URL 前缀，如 ``"/api/users"``。空字符串时路径不修改。
        deps: 保留参数（未来路由级依赖注入）。
              Reserved for future route-level dependency injection.

    Returns:
        一个类装饰器。A class decorator.

    Example::

        @router(prefix="/api/users")
        class UserRouter:
            def __init__(self, ctx: Context) -> None:
                self.db = ctx.resolve(DBService)

            @get("/")
            async def list(self) -> list[User]:
                return await self.db.list_users()
    """
    _deps = list(deps or ())

    def decorator(cls: type) -> type:
        setattr(cls, _RT_ATTR, True)
        setattr(cls, _RT_PREFIX, prefix)
        cls.__cf_router_deps__ = _deps  # type: ignore[attr-defined]
        return cls

    return decorator


def is_router(cls: type) -> bool:
    """Return ``True`` if *cls* is decorated with ``@router``."""
    return bool(getattr(cls, _RT_ATTR, False))


def get_router_prefix(cls: type) -> str:
    """Return the URL prefix declared in ``@router(prefix=...)``."""
    return getattr(cls, _RT_PREFIX, "")


# ============================================================================
# HTTP 方法装饰器工厂
# HTTP method decorator factory
# ============================================================================


def _make_route(method: str) -> Callable[..., Any]:
    """Create a decorator for a specific HTTP method.

    创建指定 HTTP 方法的装饰器。

    双层设计: 外层接收路径和额外参数，内层接收被装饰的方法。
    在方法上设置 ``_cf_route_method_`` / ``_cf_route_path_`` / ``_cf_route_kwargs_``。

    Args:
        method: 大写 HTTP 方法名 (``"GET"``, ``"POST"``, …).
    """

    def decorator[FnT: Callable[..., Any]](path: str, **kwargs: Any) -> Callable[[FnT], FnT]:
        def inner(fn: FnT) -> FnT:
            setattr(fn, _RT_ROUTE, True)
            fn._cf_route_method_ = method  # type: ignore[attr-defined]
            fn._cf_route_path_ = path  # type: ignore[attr-defined]
            fn._cf_route_kwargs_ = kwargs  # type: ignore[attr-defined]
            return fn

        return inner

    return decorator


# 从工厂函数生成所有 HTTP 方法装饰器
# Generate all HTTP method decorators from the factory
get = _make_route("GET")
"""``@get("/path")`` — 注册 GET 端点."""

post = _make_route("POST")
"""``@post("/path", status_code=201)`` — 注册 POST 端点."""

put = _make_route("PUT")
"""``@put("/path/{id}")`` — 注册 PUT 端点."""

delete = _make_route("DELETE")
"""``@delete("/path/{id}")`` — 注册 DELETE 端点."""

patch = _make_route("PATCH")
"""``@patch("/path/{id}")`` — 注册 PATCH 端点."""


# ============================================================================
# 内省工具 (Introspection helpers)
# ============================================================================


def is_route_method(fn: Callable[..., Any]) -> bool:
    """Return ``True`` if *fn* was decorated with ``@get`` / ``@post`` / …

    判断函数是否被 HTTP 方法装饰器标记。"""
    return bool(getattr(fn, _RT_ROUTE, False))


def get_route_info(fn: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
    """Extract ``(method, path, kwargs)`` from a route-decorated function.

    提取路由方法的元数据三元组。

    Args:
        fn: 被 HTTP 方法装饰器标记的函数。

    Returns:
        ``(HTTP方法, 路径, 额外参数)``。如 ``("GET", "/users", {"status_code": 200})``。
    """
    method = getattr(fn, "_cf_route_method_", "GET")
    path = getattr(fn, "_cf_route_path_", "/")
    kwargs = getattr(fn, "_cf_route_kwargs_", {})
    return method, path, kwargs
