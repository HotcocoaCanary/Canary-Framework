"""Router class — HTTP method decorators and route collection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from starlette.routing import Route

from canary_framework.common import RouteInfo
from canary_framework.core.router._utils import _route_handler
from canary_framework.engine.params import resolve_params


class Router:
    """HTTP 路由管理器。

    在 @service 类内部使用，提供 get/post/put/delete/patch 装饰器定义端点。
    自动解析路径参数和查询参数，预计算 RouteInfo 以支持 OpenAPI 文档生成。

    HTTP route manager.

    Used inside @service classes to define endpoints via get/post/put/delete/patch
    decorators. Automatically resolves path/query params and pre-computes RouteInfo
    for OpenAPI document generation.
    """

    def __init__(self, prefix: str = "", *, tags: list[str] | None = None) -> None:
        """初始化路由器。

        Args:
            prefix: 路由前缀，如 "/api/v1"。
            tags: 路由标签，自动应用于该 Router 下所有端点的 OpenAPI 分组。

        Initialize the router.

        Args:
            prefix: Route prefix, e.g., "/api/v1".
            tags: Route tags, auto-applied to OpenAPI grouping for endpoints under this Router.
        """
        self.prefix = prefix
        self.tags: list[str] = tags or []
        self._route_infos: list[RouteInfo] = []

    def _http_method(
        self,
        method: str,
        path: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        response_model: type | None = None,
        request_model: type | None = None,
        tags: list[str] | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: dict[str, object] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """内部方法：为指定 HTTP 方法注册路由。

        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE, PATCH）。
            path: 路由路径，如 "/users/{id}?page={page}"。
            summary: OpenAPI 摘要。
            description: OpenAPI 描述。
            response_model: 响应 Pydantic 模型。
            request_model: 请求体 Pydantic 模型。
            tags: OpenAPI 标签。
            deprecated: 标记为已弃用。
            operation_id: OpenAPI operationId。
            responses: 额外的响应定义。

        Returns:
            装饰器函数。

        Internal method: register a route for a given HTTP method.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            path: Route path, e.g., "/users/{id}?page={page}".
            summary: OpenAPI summary.
            description: OpenAPI description.
            response_model: Response Pydantic model.
            request_model: Request body Pydantic model.
            tags: OpenAPI tags.
            deprecated: Mark as deprecated.
            operation_id: OpenAPI operationId.
            responses: Additional response definitions.

        Returns:
            Decorator function.
        """
        from starlette.routing import compile_path

        _, starlette_path, path_regex_dict = compile_path(path)
        path_params = list(path_regex_dict.keys())

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            params = resolve_params(fn)
            param_meta: dict[str, object] = {}
            for name, (ann, has_default, field_info) in params.items():
                param_meta[name] = (ann, has_default, field_info)

            # Auto-detect request_model from handler type annotations
            effective_request_model = request_model
            if effective_request_model is None and method not in ("GET", "DELETE"):
                for pname, (pann, _, _) in params.items():
                    if pname in path_params:
                        continue
                    if isinstance(pann, type) and issubclass(pann, BaseModel):
                        effective_request_model = pann
                        break

            query_params = []
            for pname, (pann, _, _) in params.items():
                if pname not in path_params and (
                    effective_request_model is None or pann is not effective_request_model
                ):
                    query_params.append(pname)
            info = RouteInfo(
                handler=fn,
                method=method,
                path=path,
                starlette_path=starlette_path,
                path_params=path_params,
                query_params=query_params,
                param_meta=param_meta,
                summary=summary,
                description=description,
                response_model=response_model,
                request_model=effective_request_model,
                tags=tags or [],
                deprecated=deprecated,
                operation_id=operation_id,
                responses=responses or {},
                router_prefix=self.prefix,
                router_tags=list(self.tags),
            )
            self._route_infos.append(info)
            return fn

        return decorator

    def get(
        self,
        path: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        response_model: type | None = None,
        request_model: type | None = None,
        tags: list[str] | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: dict[str, object] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """注册 GET 路由。

        Register a GET route.
        """
        return self._http_method(
            "GET",
            path,
            summary=summary,
            description=description,
            response_model=response_model,
            request_model=request_model,
            tags=tags,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses,
        )

    def post(
        self,
        path: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        response_model: type | None = None,
        request_model: type | None = None,
        tags: list[str] | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: dict[str, object] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """注册 POST 路由。

        Register a POST route.
        """
        return self._http_method(
            "POST",
            path,
            summary=summary,
            description=description,
            response_model=response_model,
            request_model=request_model,
            tags=tags,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses,
        )

    def put(
        self,
        path: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        response_model: type | None = None,
        request_model: type | None = None,
        tags: list[str] | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: dict[str, object] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """注册 PUT 路由。

        Register a PUT route.
        """
        return self._http_method(
            "PUT",
            path,
            summary=summary,
            description=description,
            response_model=response_model,
            request_model=request_model,
            tags=tags,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses,
        )

    def delete(
        self,
        path: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        response_model: type | None = None,
        request_model: type | None = None,
        tags: list[str] | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: dict[str, object] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """注册 DELETE 路由。

        Register a DELETE route.
        """
        return self._http_method(
            "DELETE",
            path,
            summary=summary,
            description=description,
            response_model=response_model,
            request_model=request_model,
            tags=tags,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses,
        )

    def patch(
        self,
        path: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        response_model: type | None = None,
        request_model: type | None = None,
        tags: list[str] | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: dict[str, object] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """注册 PATCH 路由。

        Register a PATCH route.
        """
        return self._http_method(
            "PATCH",
            path,
            summary=summary,
            description=description,
            response_model=response_model,
            request_model=request_model,
            tags=tags,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses,
        )


def _collect_routes(instance: object, *, include_router_prefix: bool = False) -> list[Route]:
    """收集路由器实例中的所有路由。

    从 Router._route_infos 创建 Starlette Route 对象。

    当 include_router_prefix 为 True 时，将 Router.prefix 添加到路径前面。
    这在独立运行（无父模块）时使用，此时没有外部挂载点来处理前缀。

    Args:
        instance: 路由器实例。
        include_router_prefix: 是否在路径中包含路由器前缀。

    Returns:
        Route对象列表。

    Collect all routes from a router instance.

    Creates Starlette Route objects from Router._route_infos.

    When include_router_prefix is True, the Router.prefix is prepended
    to each route path. This is used when running standalone (no parent module)
    where there is no external mount point to handle the prefix.

    Args:
        instance: The router instance.
        include_router_prefix: Whether to include the router prefix in paths.

    Returns:
        List of Route objects.
    """
    routes: list[Route] = []
    cls = type(instance)
    router = getattr(instance, "router", None)
    if isinstance(router, Router):
        for route_info in router._route_infos:
            path = route_info.starlette_path
            if include_router_prefix and router.prefix:
                path = router.prefix + path
            routes.append(_route_handler(instance, route_info, cls, starlette_path_override=path))
    return routes


__all__ = ["Router", "_collect_routes"]
