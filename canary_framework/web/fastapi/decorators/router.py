"""路由装饰器 —— @router / @get / @post / @put / @delete / @patch。

@router:  将类声明为路由类，指定 URL 前缀
@get:     GET 请求处理器
@post:    POST 请求处理器
@put:     PUT 请求处理器
@delete:  DELETE 请求处理器
@patch:   PATCH 请求处理器

路由类构造函数接收统一 Context 对象，通过 ctx.service 访问服务，ctx.resolve() 解析依赖。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_CF_ROUTER_ATTR = "__cf_router__"  # 标记: 被 @router 装饰
_CF_ROUTER_PREFIX = "__cf_router_prefix__"  # 存储: URL 前缀
_CF_ROUTE_ATTR = "__cf_route__"  # 标记: 被 @get/@post 等装饰


def router(prefix: str = "", deps: list[type] | None = None):
    """将类声明为路由类。

    Args:
        prefix: URL 前缀，该类的所有 HTTP 方法路径会加上此前缀。
        deps: （保留参数）路由类依赖列表。

    Returns:
        内层装饰器函数。
    """
    _deps = deps or []

    def decorator(cls: type) -> type:
        setattr(cls, _CF_ROUTER_ATTR, True)
        setattr(cls, _CF_ROUTER_PREFIX, prefix)
        cls.__cf_router_deps__ = _deps  # type: ignore[attr-defined]
        return cls

    return decorator


def is_router(cls: type) -> bool:
    """判断类是否被 @router 装饰。"""
    return bool(getattr(cls, _CF_ROUTER_ATTR, False))


def get_router_prefix(cls: type) -> str:
    """获取 @router(prefix=...) 声明的 URL 前缀。"""
    return getattr(cls, _CF_ROUTER_PREFIX, "")


# ── HTTP 方法装饰器工厂 ────────────────────────────────────


def _make_route(method: str):
    """创建指定 HTTP 方法的装饰器。

    返回一个双层装饰器: 外层接收路径和额外参数，内层接收被装饰的方法。
    在方法上设置 _cf_route_method_ / _cf_route_path_ / _cf_route_kwargs_ 标记。

    Args:
        method: HTTP 方法名（GET / POST / PUT / DELETE / PATCH）。
    """

    def decorator(path: str, **kwargs: Any):
        def inner(fn: Callable[..., Any]) -> Callable[..., Any]:
            setattr(fn, _CF_ROUTE_ATTR, True)
            fn._cf_route_method_ = method  # type: ignore[attr-defined]
            fn._cf_route_path_ = path  # type: ignore[attr-defined]
            fn._cf_route_kwargs_ = kwargs  # type: ignore[attr-defined]
            return fn

        return inner

    return decorator


# HTTP 方法装饰器
get = _make_route("GET")  # @get("/users")
post = _make_route("POST")  # @post("/users", status_code=201)
put = _make_route("PUT")  # @put("/users/{id}")
delete = _make_route("DELETE")  # @delete("/users/{id}")
patch = _make_route("PATCH")  # @patch("/users/{id}")


def is_route_method(fn: Callable[..., Any]) -> bool:
    """判断函数是否被 @get/@post/@put/@delete/@patch 标记。"""
    return bool(getattr(fn, _CF_ROUTE_ATTR, False))


def get_route_info(fn: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
    """提取路由方法的元数据: (HTTP 方法, 路径, 额外参数)。

    Args:
        fn: 被 HTTP 方法装饰器标记的函数。

    Returns:
        三元组 (method, path, kwargs)，例如 ("GET", "/users", {"status_code": 200})。
    """
    method = getattr(fn, "_cf_route_method_", "GET")
    path = getattr(fn, "_cf_route_path_", "/")
    kwargs = getattr(fn, "_cf_route_kwargs_", {})
    return method, path, kwargs
