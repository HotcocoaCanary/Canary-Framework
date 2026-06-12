"""RouterBase — 基于Starlette的ASGI路由服务，支持HTTP方法装饰器。

将@service的生命周期语义与基于Starlette的路由收集相结合。
在@router类内部使用@get、@post、@put、@delete、@patch定义端点。

RouterBase — ASGI routing service with HTTP method decorator support.

Combines @service lifecycle semantics with Starlette-based route
collection. Use @get, @post, @put, @delete, @patch to define
endpoints inside a @router class.
"""

from __future__ import annotations

import warnings
from collections.abc import Awaitable, Callable
from types import FunctionType
from typing import cast

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from canary_framework.common import (
    ROUTE_ATTR,
    HookFunction,
)
from canary_framework.common.routing import parse_route_path
from canary_framework.core.service import ServiceBase
from canary_framework.engine.logging import get_logger

_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" });
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
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
    <script>
        Redoc.init("/openapi.json", {}, document.getElementById("redoc"));
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


_log = get_logger("router")


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
        # 递归转换dict或list中的Pydantic模型
        converted = _convert_to_dicts(result)
        return JSONResponse(converted)
    return PlainTextResponse(str(result))


def _convert_to_dicts(obj: object) -> object:
    """递归转换对象中的Pydantic模型为字典。

    Args:
        obj: 待转换的对象。

    Returns:
        转换后的对象。
    """
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _convert_to_dicts(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_to_dicts(item) for item in obj]
    return obj


def _route_handler(instance: object, attr: HookFunction, cls: type) -> Route:
    """创建路由处理函数。

    从类方法创建一个Starlette Route对象，自动处理响应转换和参数解析。

    支持自动参数绑定：
    - 路径参数：从URL路径提取，如 `/op/{kb_id}` 自动绑定到 `kb_id` 参数
    - 查询参数：从URL路径提取，如 `/op?count={count}#page={page}` 自动绑定到 `count` 和 `page` 参数
    - 请求体：通过request_model指定，自动解析为Pydantic模型

    Args:
        instance: 路由器实例。
        attr: 路由处理方法。
        cls: 路由器类。

    Returns:
        Starlette Route对象。

    Create a route handler.

    Creates a Starlette Route object from a class method with automatic
    response conversion and parameter parsing.

    Supports automatic parameter binding:
    - Path parameters: extracted from URL path, e.g., `/op/{kb_id}` binds to `kb_id`
    - Query parameters: extracted from URL path, e.g., `/op?count={count}#page={page}` binds to `count` and `page`
    - Request body: parsed via request_model as Pydantic model

    Args:
        instance: The router instance.
        attr: The route handler method.
        cls: The router class.

    Returns:
        Starlette Route object.
    """
    raw_info = cast("dict[str, object]", getattr(attr, ROUTE_ATTR))
    method = cast(str, raw_info["method"])
    path = cast(str, raw_info["path"])
    request_model = raw_info.get("request_model")
    handler = cast(
        "Callable[..., Awaitable[object]]",
        cast(FunctionType, attr).__get__(instance, cls),
    )

    # 解析路径，提取路径参数和查询参数
    starlette_path, path_param_names, query_param_names = parse_route_path(path)

    from canary_framework.engine.params import resolve_params

    params = resolve_params(attr)
    param_types = {name: ann for name, (ann, has_default, field_info) in params.items()}

    async def endpoint(request: Request) -> Response:
        kwargs: dict[str, object] = {}

        # 处理路径参数
        for param_name in path_param_names:
            if param_name in request.path_params:
                param_type = param_types.get(param_name)
                kwargs[param_name] = _convert_param(request.path_params[param_name], param_type)

        # 处理查询参数
        for param_name in query_param_names:
            if param_name in request.query_params:
                param_type = param_types.get(param_name)
                kwargs[param_name] = _convert_param(request.query_params[param_name], param_type)

        if request_model is not None:
            body = cast("dict[str, object]", await request.json())
            model_cls = cast("type[BaseModel]", request_model)
            parsed = model_cls(**body)
            result = await handler(parsed, **kwargs)
        else:
            result = await handler(**kwargs)

        return _auto_response(result)

    return Route(starlette_path, endpoint=endpoint, methods=[method])


def _collect_routes(instance: object) -> list[Route]:
    """收集路由器实例中的所有路由。

    扫描类的所有方法，查找带有ROUTE_ATTR属性的方法并创建路由。

    Args:
        instance: 路由器实例。

    Returns:
        Route对象列表。

    Collect all routes from a router instance.

    Scans all methods of the class, finding methods with ROUTE_ATTR attribute
    and creating routes from them.

    Args:
        instance: The router instance.

    Returns:
        List of Route objects.
    """
    routes: list[Route] = []
    cls = type(instance)
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name, None)
        if not callable(attr):
            continue
        if not hasattr(attr, ROUTE_ATTR):
            continue
        routes.append(_route_handler(instance, attr, cls))
    return routes


class RouterBase(ServiceBase):
    """@router装饰类的自动注入基类（已弃用）。

    路由能力已下沉到 ServiceBase。请直接继承 ServiceBase 并使用 @service(prefix=..., tags=...)
    替代 @router(prefix=..., tags=...)。RouterBase 将在未来版本中移除。

    当前 RouterBase 作为 ServiceBase 的薄包装器保持向后兼容。

    Auto-injected base for @router-decorated classes (deprecated).

    Routing capabilities have been moved to ServiceBase. Please inherit from
    ServiceBase directly and use @service(prefix=..., tags=...) instead of
    @router(prefix=..., tags=...). RouterBase will be removed in a future version.

    Currently RouterBase acts as a thin wrapper around ServiceBase for backward
    compatibility.
    """

    def __init__(self) -> None:
        """初始化RouterBase实例（已弃用）。

        Initializes the RouterBase instance (deprecated).
        """

        warnings.warn(
            "RouterBase is deprecated. Use ServiceBase with @service(prefix=..., tags=...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()


__all__ = ["RouterBase"]
