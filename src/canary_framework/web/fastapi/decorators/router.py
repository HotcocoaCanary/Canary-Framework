"""HTTP route decorators — ``@router``, ``@get``, ``@post``, ``@put``, ``@delete``, ``@patch``.

设计思路 (Design rationale):
    ``@router`` 内部调用 ``@service``，因此 Router 是框架中的一等服务——拥有 DI、
    配置和生命周期。 与 ``@module`` 同构：先 ``service()`` 设基础标记，
    再覆盖 ``__cf_service_meta__`` 为 :class:`RouterMeta`。

    ``@get`` / ``@post`` 等显式接收 8 个精选参数，而非 ``**kwargs`` 透传给
    FastAPI。用户看到的是 Canary 的 API 面，不需要了解 FastAPI 内部。

    路由注册使用 FastAPI 原生 ``APIRouter`` + ``include_router``，
    prefix/tags 由 FastAPI 处理，避免手动字符串操作。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from canary_framework.common._types import RouterMeta
from canary_framework.core.algorithms.naming import to_snake
from canary_framework.core.decorators.service import (
    _SERVICE_META,
    service,
)

# ============================================================================
# 标记属性 (Marker attributes)
# ============================================================================

_RT_ATTR = "__cf_router__"
"""Set to ``True`` on classes decorated with ``@router``."""

_RT_ROUTE = "__cf_route__"
"""Set to ``True`` on methods decorated with ``@get`` / ``@post`` / …."""


# ============================================================================
# @router 装饰器
# ============================================================================


def router(
    prefix: str = "",
    *,
    name: str | None = None,
    deps: list[type] | None = None,
    tags: list[str] | None = None,
) -> Callable[[type], type]:
    """Mark a class as a Canary route handler (a specialised service).

    将类声明为路由处理器（特殊的框架服务）。内部调用 ``@service``，
    因此 Router 拥有完整的 DI 和生命周期支持。

    Args:
        prefix: URL 前缀，应用于该路由组所有端点。
        name: 服务名称，默认根据类名自动生成 snake_case。
        deps: 依赖的 ``@service`` / ``@module`` 类列表，通过 DI 注入。
        tags: OpenAPI 文档标签，应用于该路由组所有端点（可在端点级覆盖）。

    Returns:
        一个类装饰器。A class decorator.

    Example::

        @router(prefix="/api/users", deps=[UserService], tags=["users"])
        class UserRouter:
            user_service: UserService

            @get("/{id}", response_model=User)
            async def get(self, id: int) -> User:
                return await self.user_service.get_by_id(id)
    """
    _prefix = prefix
    _deps = list(deps or ())
    _tags = list(tags or ())
    _name = name

    def decorator(cls: type) -> type:
        svc_name = _name or to_snake(cls.__name__)
        service(name=svc_name, deps=_deps)(cls)
        meta = RouterMeta(
            name=svc_name,
            deps=_deps,
            prefix=_prefix,
            tags=_tags,
        )
        setattr(cls, _SERVICE_META, meta)
        setattr(cls, _RT_ATTR, True)
        return cls

    return decorator


def is_router(cls: type) -> bool:
    """Return ``True`` if *cls* is decorated with ``@router``."""
    return bool(getattr(cls, _RT_ATTR, False))


def get_router_meta(cls: type) -> RouterMeta:
    """Return the :class:`RouterMeta` instance from a ``@router``-decorated class."""
    raw: object = getattr(cls, _SERVICE_META, None)
    if isinstance(raw, RouterMeta):
        return raw
    return RouterMeta(name="")


# ============================================================================
# HTTP 方法装饰器工厂 — 显式参数替代 **kwargs 透传
# HTTP method decorator factory — explicit params instead of **kwargs proxy
# ============================================================================

# 精选 FastAPI APIRouter 20+ 参数中 95%+ 真实项目会用到的高频参数。
# 其余高级参数（response_model_exclude, openapi_extra 等）极少使用，
# 确有需要时直接使用原始 FastAPI。
#
# Curated subset of FastAPI's APIRouter route params covering 95%+ of real usage.
# Rare advanced params like response_model_exclude / openapi_extra are omitted;
# users who need them can use raw FastAPI directly.


_FnT = TypeVar("_FnT", bound=Callable[..., Any])
"""Type variable for the decorated function."""


def _make_route(method: str) -> Callable[..., Callable[[_FnT], _FnT]]:
    """Create a decorator for a specific HTTP method.

    创建指定 HTTP 方法的装饰器。显式声明 8 个筛选后的参数，
    不接收 ``**kwargs``——用户看到的是 Canary 的 API 面。

    Args:
        method: 大写 HTTP 方法名 (``"GET"``, ``"POST"``, …).
    """

    def decorator(
        path: str,
        *,
        response_model: type | None = None,
        status_code: int | None = None,
        summary: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        dependencies: list[object] | None = None,
        deprecated: bool | None = None,
        response_description: str | None = None,
    ) -> Callable[[_FnT], _FnT]:
        # 只保留非 None 的参数，避免将 None 传给 FastAPI 覆盖其默认行为
        # Filter to non-None values — passing None to FastAPI may override defaults
        opts: dict[str, Any] = {
            k: v
            for k, v in {
                "response_model": response_model,
                "status_code": status_code,
                "summary": summary,
                "description": description,
                "tags": tags,
                "dependencies": dependencies,
                "deprecated": deprecated,
                "response_description": response_description,
            }.items()
            if v is not None
        }

        def inner(fn: _FnT) -> _FnT:
            setattr(fn, _RT_ROUTE, True)
            fn._cf_route_method_ = method  # type: ignore[attr-defined]
            fn._cf_route_path_ = path  # type: ignore[attr-defined]
            fn._cf_route_kwargs_ = opts  # type: ignore[attr-defined]
            return fn

        return inner

    return decorator


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
    method: str = getattr(fn, "_cf_route_method_", "GET")
    path: str = getattr(fn, "_cf_route_path_", "/")
    kwargs: dict[str, Any] = getattr(fn, "_cf_route_kwargs_", {})
    return method, path, kwargs
