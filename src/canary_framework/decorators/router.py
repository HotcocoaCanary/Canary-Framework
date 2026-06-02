"""@router装饰器和HTTP方法装饰器实现。

提供路由定义功能，支持GET、POST、PUT、DELETE、PATCH方法。

@router decorator and HTTP method decorators implementation.

Provides routing definition functionality with GET, POST, PUT, DELETE, PATCH methods.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import (
    CF_ROUTER_MARKER,
    ROUTE_ATTR,
    HookFunction,
    RouterMeta,
)
from canary_framework.core import RouterBase
from canary_framework.engine import make_subclass


def _http_method(
    method: str,
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    path_params: dict[str, object] | None = None,
    query_params: dict[str, object] | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]:
    """创建HTTP方法装饰器。

    存储完整的OpenAPI路由元数据到ROUTE_ATTR中。

    Creates an HTTP method decorator.

    Stores full OpenAPI route metadata in ROUTE_ATTR.
    """

    def decorator(fn: HookFunction) -> HookFunction:
        info: dict[str, object] = {
            "method": method,
            "path": path,
        }
        if summary is not None:
            info["summary"] = summary
        if description is not None:
            info["description"] = description
        if response_model is not None:
            info["response_model"] = response_model
        if request_model is not None:
            info["request_model"] = request_model
        if path_params is not None:
            info["path_params"] = path_params
        if query_params is not None:
            info["query_params"] = query_params
        if tags is not None:
            info["tags"] = tags
        if deprecated:
            info["deprecated"] = deprecated
        if operation_id is not None:
            info["operation_id"] = operation_id
        if responses is not None:
            info["responses"] = responses
        setattr(fn, ROUTE_ATTR, info)
        return fn

    return decorator


def get(
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    path_params: dict[str, object] | None = None,
    query_params: dict[str, object] | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]:
    """将异步方法标记为GET路由处理器。

    Mark an async method as a GET route handler.
    """
    return _http_method(
        "GET",
        path,
        summary=summary,
        description=description,
        response_model=response_model,
        request_model=request_model,
        path_params=path_params,
        query_params=query_params,
        tags=tags,
        deprecated=deprecated,
        operation_id=operation_id,
        responses=responses,
    )


def post(
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    path_params: dict[str, object] | None = None,
    query_params: dict[str, object] | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]:
    """将异步方法标记为POST路由处理器。

    Mark an async method as a POST route handler.
    """
    return _http_method(
        "POST",
        path,
        summary=summary,
        description=description,
        response_model=response_model,
        request_model=request_model,
        path_params=path_params,
        query_params=query_params,
        tags=tags,
        deprecated=deprecated,
        operation_id=operation_id,
        responses=responses,
    )


def put(
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    path_params: dict[str, object] | None = None,
    query_params: dict[str, object] | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]:
    """将异步方法标记为PUT路由处理器。

    Mark an async method as a PUT route handler.
    """
    return _http_method(
        "PUT",
        path,
        summary=summary,
        description=description,
        response_model=response_model,
        request_model=request_model,
        path_params=path_params,
        query_params=query_params,
        tags=tags,
        deprecated=deprecated,
        operation_id=operation_id,
        responses=responses,
    )


def delete(
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    path_params: dict[str, object] | None = None,
    query_params: dict[str, object] | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]:
    """将异步方法标记为DELETE路由处理器。

    Mark an async method as a DELETE route handler.
    """
    return _http_method(
        "DELETE",
        path,
        summary=summary,
        description=description,
        response_model=response_model,
        request_model=request_model,
        path_params=path_params,
        query_params=query_params,
        tags=tags,
        deprecated=deprecated,
        operation_id=operation_id,
        responses=responses,
    )


def patch(
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    path_params: dict[str, object] | None = None,
    query_params: dict[str, object] | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]:
    """将异步方法标记为PATCH路由处理器。

    Mark an async method as a PATCH route handler.
    """
    return _http_method(
        "PATCH",
        path,
        summary=summary,
        description=description,
        response_model=response_model,
        request_model=request_model,
        path_params=path_params,
        query_params=query_params,
        tags=tags,
        deprecated=deprecated,
        operation_id=operation_id,
        responses=responses,
    )


def router(
    prefix: str = "",
    *,
    deps: list[type] | None = None,
    tags: list[str] | None = None,
) -> Callable[[type], type[RouterBase]]:
    """声明一个类为路由服务。

    将@service语义与HTTP路由分组相结合。
    路由名称自动生成为``类名 + Router``。

    Args:
        prefix: 应用于此组中所有路由的URL前缀。
        deps: 依赖类列表。
        tags: 此路由组的OpenAPI标签。

    Returns:
        装饰后的类。

    Declare a class as a Canary Framework router service.

    Combines ``@service`` semantics with HTTP route grouping.
    The router name is auto-generated as ``ClassName + Router``.

    Args:
        prefix: URL prefix applied to all routes in this group.
        deps: Dependency classes.
        tags: OpenAPI tags for this route group.

    Returns:
        The decorated class.
    """
    _deps = list(deps or ())
    _tags = list(tags or [])

    def decorator(cls: type) -> type[RouterBase]:
        name = cls.__name__ + "Router"
        routes: list[HookFunction] = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if callable(attr) and hasattr(attr, ROUTE_ATTR):
                routes.append(attr)

        meta = RouterMeta(
            name=name,
            deps=_deps,
            prefix=prefix,
            tags=_tags,
            routes=routes,
        )

        return cast(
            "type[RouterBase]",
            make_subclass(cls, RouterBase, meta, name, extra_marker=CF_ROUTER_MARKER),
        )

    return decorator


__all__ = [
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "router",
]
