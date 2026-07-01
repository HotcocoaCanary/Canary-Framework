"""Router utilities — route handling, response conversion, doc building, path parsing."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from types import UnionType
from typing import cast

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from canary_framework.common import ResolvedRoute

_PARAM_PATTERN = r"\{(\w+)\}"


def parse_route_path(path: str) -> tuple[str, list[str], list[str]]:
    """Parse a route path to extract path parameters and query parameters."""
    parts = path.split("?", 1)
    base_path = parts[0]
    path_params = re.findall(_PARAM_PATTERN, base_path)

    query_params: list[str] = []
    if len(parts) > 1:
        query_params = re.findall(_PARAM_PATTERN, parts[1])
    return base_path, path_params, query_params


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


_BOOL_TRUE = frozenset({"1", "true", "yes", "on"})
_BOOL_FALSE = frozenset({"0", "false", "no", "off"})


def _convert_param(value: str, param_type: type | UnionType | None) -> object:
    """将字符串参数转换为目标类型。

    解包 Optional[T] 后按内层类型转换；bool 接受常见真假拼写，
    无法识别时抛 ValueError（由调用方转 422）。

    Convert a string param to its target type. Unwraps Optional[T];
    bool accepts common spellings and raises ValueError on unrecognized
    input.

    Args:
        value: 原始字符串值 / original string value
        param_type: 目标类型 / target type

    Returns:
        转换后的值 / converted value
    """
    from canary_framework.common import unwrap_optional

    param_type, _ = unwrap_optional(param_type)
    if param_type is None or param_type is str:
        return value
    if param_type is bool:
        low = value.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        raise ValueError(f"Invalid boolean value: {value!r}")
    if param_type is int:
        return int(value)
    if param_type is float:
        return float(value)
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
    - (body, status_code) 二元组：根据body类型选择响应，并设置状态码
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
    - (body, status_code) tuple: selects response type based on body and sets status code
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
    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], int)
        and not isinstance(result[1], bool)
    ):
        body, status_code = result
        if isinstance(body, Response):
            body.status_code = status_code
            return body
        if isinstance(body, BaseModel):
            return JSONResponse(body.model_dump(), status_code=status_code)
        if isinstance(body, (dict, list)):
            return JSONResponse(_convert_nested_models(body), status_code=status_code)
        if isinstance(body, str):
            return PlainTextResponse(body, status_code=status_code)
        return PlainTextResponse(str(body), status_code=status_code)
    if isinstance(result, str):
        return PlainTextResponse(result)
    if isinstance(result, BaseModel):
        return JSONResponse(result.model_dump())
    if isinstance(result, (dict, list)):
        converted = _convert_nested_models(result)
        return JSONResponse(converted)
    return PlainTextResponse(str(result))


def _check_route_collisions(routes: list[ResolvedRoute]) -> None:
    """检测 (method, full_path) 冲突，重复则抛错。

    Detect duplicate (method, full_path) routes and raise on collision.
    """
    seen: set[tuple[str, str]] = set()
    for r in routes:
        key = (r.info.method, r.full_path)
        if key in seen:
            raise ValueError(f"Route collision: {r.info.method} {r.full_path}")
        seen.add(key)


def _build_route(resolved: ResolvedRoute) -> Route:
    """从 ResolvedRoute 构建 Starlette Route，全程按参数名绑定。

    Build a Starlette Route from a ResolvedRoute, binding everything by name.
    """
    info = resolved.info
    handler = cast("Callable[..., Awaitable[object]]", resolved.handler)
    param_types: dict[str, type | None] = {
        name: cast("type | None", meta[0])  # type: ignore[index]
        for name, meta in info.param_meta.items()
    }

    def _required(name: str) -> bool:
        meta = info.param_meta.get(name)
        return not (meta and meta[1])  # type: ignore[index]

    async def endpoint(request: Request) -> Response:
        kwargs: dict[str, object] = {}
        errors: list[dict[str, str]] = []

        for name in info.path_params:
            if name in request.path_params:
                try:
                    kwargs[name] = _convert_param(request.path_params[name], param_types.get(name))
                except (ValueError, TypeError):
                    return JSONResponse(
                        {"detail": f"Invalid value for path parameter '{name}'"},
                        status_code=400,
                    )

        for name in info.query_params:
            if name in request.query_params:
                try:
                    kwargs[name] = _convert_param(request.query_params[name], param_types.get(name))
                except (ValueError, TypeError):
                    errors.append({"param": name, "msg": "invalid value"})
            elif _required(name):
                errors.append({"param": name, "msg": "missing required query parameter"})

        if errors:
            return JSONResponse({"detail": errors}, status_code=422)

        if info.request_model is not None and info.body_param is not None:
            try:
                body = cast("dict[str, object]", await request.json())
            except Exception:
                return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)
            model_cls = cast("type[BaseModel]", info.request_model)
            try:
                kwargs[info.body_param] = model_cls(**body)
            except ValidationError as e:
                return JSONResponse({"detail": e.errors()}, status_code=422)

        return _auto_response(await handler(**kwargs))

    return Route(resolved.full_path, endpoint=endpoint, methods=[info.method])


def _build_doc_routes(
    schema: dict[str, object],
    *,
    openapi_path: str = "/openapi.json",
    swagger_path: str = "/docs",
    redoc_path: str = "/redoc",
    swagger_css: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    swagger_js: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    redoc_js: str = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
) -> list[Route]:
    """构建 OpenAPI 文档端点路由。

    创建三个端点：
    - openapi_path: 提供 OpenAPI JSON schema
    - swagger_path: 提供 Swagger UI 页面
    - redoc_path: 提供 ReDoc 页面

    Args:
        schema: OpenAPI 3.0.3 schema 字典。
        openapi_path: OpenAPI JSON 端点路径。
        swagger_path: Swagger UI 页面路径。
        redoc_path: ReDoc 页面路径。
        swagger_css: Swagger UI CSS CDN URL。
        swagger_js: Swagger UI JS CDN URL。
        redoc_js: ReDoc JS CDN URL。

    Returns:
        Starlette Route 对象列表。

    Build OpenAPI documentation endpoint routes.

    Creates three endpoints:
    - openapi_path: Serves the OpenAPI JSON schema
    - swagger_path: Serves the Swagger UI page
    - redoc_path: Serves the ReDoc page

    Args:
        schema: OpenAPI 3.0.3 schema dict.
        openapi_path: OpenAPI JSON endpoint path.
        swagger_path: Swagger UI page path.
        redoc_path: ReDoc page path.
        swagger_css: Swagger UI CSS CDN URL.
        swagger_js: Swagger UI JS CDN URL.
        redoc_js: ReDoc JS CDN URL.

    Returns:
        List of Starlette Route objects.
    """
    routes: list[Route] = []

    async def openapi_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(schema)

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
    "_build_route",
    "_check_route_collisions",
    "_convert_nested_models",
    "_convert_param",
    "parse_route_path",
]
