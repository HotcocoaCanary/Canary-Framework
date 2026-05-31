"""RouterBase — 基于Starlette的ASGI路由服务，支持HTTP方法装饰器。

将@service的生命周期语义与基于Starlette的路由收集相结合。
在@router类内部使用@get、@post、@put、@delete、@patch定义端点。

RouterBase — ASGI routing service with HTTP method decorator support.

Combines @service lifecycle semantics with Starlette-based route
collection. Use @get, @post, @put, @delete, @patch to define
endpoints inside a @router class.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.routing import Router as StarletteRouter
from starlette.types import ASGIApp, Receive, Scope, Send

from canary_framework.common import ROUTE_ATTR, HookFunction
from canary_framework.core.service import ServiceBase


def _auto_response(result: object) -> Response:
    """自动将返回值转换为Starlette响应对象。

    根据返回值类型自动选择合适的响应类型：
    - Response对象：直接返回
    - dict或list：返回JSONResponse
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
    - str: PlainTextResponse
    - other types: PlainTextResponse with string representation

    Args:
        result: The return value from the route handler.

    Returns:
        Starlette Response object.
    """
    if isinstance(result, Response):
        return result
    if isinstance(result, (dict, list)):
        return JSONResponse(result)
    if isinstance(result, str):
        return PlainTextResponse(result)
    return PlainTextResponse(str(result))


def _route_handler(instance: object, attr: HookFunction, cls: type) -> Route:
    """创建路由处理函数。

    从类方法创建一个Starlette Route对象，自动处理响应转换。

    Args:
        instance: 路由器实例。
        attr: 路由处理方法。
        cls: 路由器类。

    Returns:
        Starlette Route对象。

    Create a route handler.

    Creates a Starlette Route object from a class method with automatic
    response conversion.

    Args:
        instance: The router instance.
        attr: The route handler method.
        cls: The router class.

    Returns:
        Starlette Route object.
    """
    raw_info: dict[str, str] = getattr(attr, ROUTE_ATTR)
    method: str = raw_info["method"]
    path: str = raw_info["path"]
    handler = cast(
        "Callable[..., Awaitable[object]]",
        # pyright: ignore[reportAttributeAccessIssue]
        attr.__get__(instance, cls),  # ty:ignore[unresolved-attribute]
    )

    async def endpoint(request: object) -> Response:
        result = await handler(request)
        return _auto_response(result)

    return Route(path, endpoint=endpoint, methods=[method])


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
            self._starlette_router = StarletteRouter(_collect_routes(self))
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