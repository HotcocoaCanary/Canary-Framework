"""RouterBase — ASGI routing service with HTTP method decorator support.

Combines ``@service`` lifecycle semantics with Starlette-based route
collection.  Use ``@get``, ``@post``, ``@put``, ``@delete``, ``@patch``
to define endpoints inside a ``@router`` class.
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
    if isinstance(result, Response):
        return result
    if isinstance(result, (dict, list)):
        return JSONResponse(result)
    if isinstance(result, str):
        return PlainTextResponse(result)
    return PlainTextResponse(str(result))


def _route_handler(instance: object, attr: HookFunction, cls: type) -> Route:
    raw_info: dict[str, str] = getattr(attr, ROUTE_ATTR)
    method: str = raw_info["method"]
    path: str = raw_info["path"]
    handler = cast(
        "Callable[..., Awaitable[object]]",
        attr.__get__(instance, cls),
    )

    async def endpoint(request: object) -> Response:
        result = await handler(request)
        return _auto_response(result)

    return Route(path, endpoint=endpoint, methods=[method])


def _collect_routes(instance: object) -> list[Route]:
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
    """Auto-injected base for ``@router``-decorated classes."""

    def __init__(self) -> None:
        super().__init__()
        self._starlette_router: StarletteRouter | None = None

    @property
    def asgi_app(self) -> ASGIApp:
        if self._starlette_router is None:
            self._starlette_router = StarletteRouter(_collect_routes(self))
        return self._starlette_router

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.asgi_app(scope, receive, send)


__all__ = ["RouterBase"]
