"""RouterBase — 基于Starlette的ASGI路由服务，支持HTTP方法装饰器。

将@service的生命周期语义与基于Starlette的路由收集相结合。
在@router类内部使用@get、@post、@put、@delete、@patch定义端点。

RouterBase — ASGI routing service with HTTP method decorator support.

Combines @service lifecycle semantics with Starlette-based route
collection. Use @get, @post, @put, @delete, @patch to define
endpoints inside a @router class.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from types import FunctionType
from typing import cast, get_type_hints

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.routing import Router as StarletteRouter
from starlette.types import ASGIApp, Receive, Scope, Send

from canary_framework.common import ROUTE_ATTR, HookFunction
from canary_framework.common.markers import get_router_meta
from canary_framework.core.service import ServiceBase
from canary_framework.engine.logging import get_logger


def _parse_route_path(path: str) -> tuple[str, list[str], list[str]]:
    """解析路由路径，提取路径参数和查询参数。

    路径格式：
    - 路径参数：{param}，如 /op/{kb_id}
    - 查询参数：?param={param} 或 #param={param}

    Args:
        path: 路由路径，如 "/op/{kb_id}?count={count}#page={page}"

    Returns:
        (starlette_path, path_params, query_params)
        - starlette_path: Starlette兼容的路径，如 "/op/{kb_id}"
        - path_params: 路径参数名称列表，如 ["kb_id"]
        - query_params: 查询参数名称列表，如 ["count", "page"]
    """
    pattern = r"\{(\w+)\}"

    # 分离路径部分和查询参数部分
    base_path = path.split("?")[0].split("#")[0]

    # 提取路径参数（在基础路径中的 {param}）
    path_params = re.findall(pattern, base_path)

    # 提取查询参数（在 ? 或 # 后面的 {param}）
    query_params: list[str] = []

    # 查找 ? 后的查询参数
    if "?" in path:
        query_part = path.split("?")[1]
        # 去掉 # 后面的部分
        if "#" in query_part:
            query_part = query_part.split("#")[0]
        query_params.extend(re.findall(pattern, query_part))

    # 查找 # 后的查询参数
    if "#" in path:
        hash_part = path.split("#")[1]
        # 去掉 ? 后面的部分（如果 # 在 ? 前面）
        if "?" in hash_part:
            hash_part = hash_part.split("?")[0]
        query_params.extend(re.findall(pattern, hash_part))

    return base_path, path_params, query_params


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
    starlette_path, path_param_names, query_param_names = _parse_route_path(path)

    # 应用路由器前缀
    router_meta = get_router_meta(cls)
    if router_meta and router_meta.prefix:
        starlette_path = router_meta.prefix + starlette_path

    sig = inspect.signature(attr)
    try:
        type_hints = get_type_hints(attr)
    except Exception:
        type_hints = {}

    param_types = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if name in type_hints:
            param_types[name] = type_hints[name]
        elif param.annotation is not inspect.Parameter.empty:
            param_types[name] = param.annotation
        else:
            param_types[name] = None

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
    """@router装饰类的自动注入基类。

    Auto-injected base for @router-decorated classes.
    """

    def __init__(self) -> None:
        """初始化RouterBase实例。

        Initializes the RouterBase instance.
        """
        super().__init__()
        self._starlette_router: StarletteRouter | None = None

    @property
    def asgi_app(self) -> ASGIApp:
        """获取ASGI应用。

        懒加载创建Starlette路由器，收集所有路由。

        Returns:
            StarletteRouter实例。

        Get the ASGI application.

        Lazily creates the Starlette router and collects all routes.

        Returns:
            StarletteRouter instance.
        """
        if self._starlette_router is None:
            routes = _collect_routes(self)
            _log.debug("Collected %d route(s) for router: %s", len(routes), type(self).__name__)
            for route in routes:
                _log.debug("  Route: %s %s", route.methods, route.path)
            self._starlette_router = StarletteRouter(routes)
        return self._starlette_router

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI应用入口点。

        将请求委托给asgi_app处理。

        Args:
            scope: ASGI scope字典。
            receive: 接收消息的异步函数。
            send: 发送消息的异步函数。

        ASGI application entry point.

        Delegates requests to the asgi_app.

        Args:
            scope: ASGI scope dictionary.
            receive: Async function to receive messages.
            send: Async function to send messages.
        """
        await self.asgi_app(scope, receive, send)


__all__ = ["RouterBase"]
