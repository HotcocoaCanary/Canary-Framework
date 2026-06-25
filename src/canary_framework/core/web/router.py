"""Router utilities — route handling, response conversion, doc building, path parsing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import FunctionType
from typing import Any, cast

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from canary_framework.common import RouteDef
from canary_framework.core.params import EndpointMeta

_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Swagger UI</title>
    <link rel="stylesheet" href="{swagger_css}">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="{swagger_js}"></script>
    <script>
        SwaggerUIBundle({{ url: "{openapi_path}", dom_id: "#swagger-ui" }});
    </script>
</body>
</html>"""

_REDOC_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>ReDoc</title>
</head>
<body>
    <div id="redoc"></div>
    <script src="{redoc_js}"></script>
    <script>
        Redoc.init("{openapi_path}", {{}}, document.getElementById("redoc"));
    </script>
</body>
</html>"""


def _convert_param(value: str, param_type: type | None) -> object:
    """将字符串参数转换为目标类型。

    Args:
        value: 原始字符串值
        param_type: 目标类型

    Returns:
        转换后的值
    """
    if param_type is None or param_type is str:
        return value
    if param_type is int:
        return int(value)
    if param_type is float:
        return float(value)
    if param_type is bool:
        return value.lower() == "true"
    return value


def _convert_nested_models(obj: object) -> object:
    """递归转换对象中的Pydantic模型为字典。

    Args:
        obj: 待转换的对象。

    Returns:
        转换后的对象。
    """
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _convert_nested_models(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_nested_models(item) for item in obj]
    return obj


def _auto_response(result: object) -> Response:
    """自动将返回值转换为Starlette响应对象。

    根据返回值类型自动选择合适的响应类型：
    - Response对象：直接返回
    - dict或list：返回JSONResponse
    - Pydantic BaseModel：返回JSONResponse（调用model_dump）
    - str：返回PlainTextResponse
    - 其他类型：转换为字符串后返回PlainTextResponse

    Args:
        result: 路由处理函数的返回值。

    Returns:
        Starlette Response对象。

    Auto-convert return value to Starlette response.

    Automatically selects the appropriate response type based on the return value:
    - Response object: returned directly
    - dict or list: JSONResponse
    - Pydantic BaseModel: JSONResponse (via model_dump)
    - str: PlainTextResponse
    - other types: PlainTextResponse with string representation

    Args:
        result: The return value from the route handler.

    Returns:
        Starlette Response object.
    """
    if isinstance(result, Response):
        return result
    if isinstance(result, str):
        return PlainTextResponse(result)
    if isinstance(result, BaseModel):
        return JSONResponse(result.model_dump())
    if isinstance(result, (dict, list)):
        converted = _convert_nested_models(result)
        return JSONResponse(converted)
    return PlainTextResponse(str(result))


def _route_handler(
    instance: object,
    route_def: RouteDef,
    endpoint_meta: EndpointMeta,
    cls: type,
    *,
    starlette_path_override: str | None = None,
) -> Route:
    from starlette.concurrency import run_in_threadpool

    method = route_def.method
    starlette_path = (
        starlette_path_override if starlette_path_override is not None else route_def.path
    )
    handler = cast(
        "Callable[..., Awaitable[object]]",
        cast(FunctionType, endpoint_meta.call).__get__(instance, cls),
    )

    async def endpoint(request: Request) -> Response:
        kwargs: dict[str, object] = {}

        # 1. Extract path & query
        try:
            for p_name, meta in endpoint_meta.path_params.items():
                if p_name in request.path_params:
                    kwargs[p_name] = _convert_param(request.path_params[p_name], meta[0])
            for p_name, meta in endpoint_meta.query_params.items():
                if p_name in request.query_params:
                    kwargs[p_name] = _convert_param(request.query_params[p_name], meta[0])
        except (ValueError, TypeError) as e:
            return JSONResponse({"detail": str(e)}, status_code=400)

        # 2. Inject implicit variables
        if endpoint_meta.request_param_name:
            kwargs[endpoint_meta.request_param_name] = request

        # 3. Handle body
        if endpoint_meta.body_model:
            try:
                body_json = cast("dict[str, object]", await request.json())
                parsed = endpoint_meta.body_model(**body_json)
            except ValidationError as e:
                return JSONResponse({"detail": e.errors()}, status_code=422)
            except Exception:
                return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)

            if endpoint_meta.body_param_name:
                kwargs[endpoint_meta.body_param_name] = parsed
            else:
                kwargs["__unnamed_body__"] = parsed

        unnamed_body = kwargs.pop("__unnamed_body__", None)

        if endpoint_meta.is_coroutine:
            if unnamed_body is not None:
                result = await handler(unnamed_body, **kwargs)
            else:
                result = await handler(**kwargs)
        else:

            def sync_call() -> Any:
                if unnamed_body is not None:
                    return handler(unnamed_body, **kwargs)
                return handler(**kwargs)

            result = await run_in_threadpool(sync_call)

        return _auto_response(result)

    return Route(starlette_path, endpoint=endpoint, methods=[method])


def _build_doc_routes(
    schema_factory: Callable[[], dict[str, object]],
    *,
    openapi_path: str = "/openapi.json",
    swagger_path: str = "/docs",
    redoc_path: str = "/redoc",
    swagger_css: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    swagger_js: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    redoc_js: str = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
) -> list[Route]:
    routes: list[Route] = []
    _cached_schema: dict[str, object] | None = None

    async def openapi_endpoint(request: Request) -> JSONResponse:
        nonlocal _cached_schema
        if _cached_schema is None:
            _cached_schema = schema_factory()
        return JSONResponse(_cached_schema)

    routes.append(Route(openapi_path, endpoint=openapi_endpoint, methods=["GET"]))

    swagger_html = _SWAGGER_UI_HTML.format(
        swagger_css=swagger_css,
        swagger_js=swagger_js,
        openapi_path=openapi_path,
    )

    async def swagger_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(swagger_html)

    routes.append(Route(swagger_path, endpoint=swagger_endpoint, methods=["GET"]))

    redoc_html = _REDOC_HTML.format(
        redoc_js=redoc_js,
        openapi_path=openapi_path,
    )

    async def redoc_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(redoc_html)

    routes.append(Route(redoc_path, endpoint=redoc_endpoint, methods=["GET"]))

    return routes


__all__ = [
    "_auto_response",
    "_build_doc_routes",
    "_convert_nested_models",
    "_convert_param",
    "_route_handler",
]


"""Router class — HTTP method decorators and route collection."""


class Router:
    """HTTP 路由管理器。

    在 @service 类内部使用，提供 get/post/put/delete/patch 装饰器定义端点。
    自动解析路径参数和查询参数，预计算 RouteInfo 以支持 OpenAPI 文档生成。

    HTTP route manager.

    Used inside @service classes to define endpoints via get/post/put/delete/patch
    decorators. Automatically resolves path/query params and pre-computes RouteDef
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
        self._route_defs: list[RouteDef] = []

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

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            info = RouteDef(
                handler=fn,
                method=method,
                path=path,
                summary=summary,
                description=description,
                response_model=response_model,
                request_model=request_model,
                tags=tags or [],
                deprecated=deprecated,
                operation_id=operation_id,
                responses=responses or {},
                router_prefix=self.prefix,
                router_tags=list(self.tags),
            )
            self._route_defs.append(info)
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

    从 Router._route_defs 创建 Starlette Route 对象。

    当 include_router_prefix 为 True 时，将 Router.prefix 添加到路径前面。
    这在独立运行（无父模块）时使用，此时没有外部挂载点来处理前缀。

    Args:
        instance: 路由器实例。
        include_router_prefix: 是否在路径中包含路由器前缀。

    Returns:
        Route对象列表。

    Collect all routes from a router instance.

    Creates Starlette Route objects from Router._route_defs.

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
        for route_def in router._route_defs:
            from starlette.routing import compile_path

            from canary_framework.core.params import resolve_endpoint_meta

            endpoint_meta = resolve_endpoint_meta(
                path=route_def.path,
                call=route_def.handler,
                is_endpoint=True,
                request_model=route_def.request_model,
                http_method=route_def.method,
            )
            _, starlette_path, _ = compile_path(route_def.path)
            if include_router_prefix and router.prefix:
                starlette_path = router.prefix + starlette_path

            routes.append(
                _route_handler(
                    instance, route_def, endpoint_meta, cls, starlette_path_override=starlette_path
                )
            )
    return routes


__all__ = ["Router", "_collect_routes"]
