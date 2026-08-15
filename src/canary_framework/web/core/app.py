"""Web app builder — assemble a unit's routes into a Starlette app.

app 构建：从单个 ``@web_cocoa`` 单元收集 ``@get``/``@post`` 路由，组装成 Starlette
应用，并挂载 ``/openapi.json``、``/docs``、``/redoc``。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from canary_framework.common.markers import WEB_ATTR
from canary_framework.web.core.openapi import REDOC_HTML, SWAGGER_UI_HTML, build_openapi
from canary_framework.web.core.routing import dispatch
from canary_framework.web.decorator.introspect import routes_of
from canary_framework.web.error.web import RouteRegistrationError

_DEFAULT_TITLE = "Canary API"
_DEFAULT_VERSION = "0.1.0"


def build_web_app(instance: object) -> Starlette:
    """Collect *instance*'s routes and build a Starlette app plus its OpenAPI doc."""
    meta = getattr(type(instance), WEB_ATTR, {})
    title = meta.get("title", _DEFAULT_TITLE)
    version = meta.get("version", _DEFAULT_VERSION)
    routes = _collect_routes(instance)

    async def openapi_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(build_openapi(title, version, routes))

    async def docs_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(SWAGGER_UI_HTML)

    async def redoc_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(REDOC_HTML)

    app_routes: list[Route] = [
        Route("/openapi.json", openapi_endpoint, methods=["GET"]),
        Route("/docs", docs_endpoint, methods=["GET"]),
        Route("/redoc", redoc_endpoint, methods=["GET"]),
    ]
    for method, path, _instance, fn in routes:
        app_routes.append(Route(path, _make_endpoint(instance, fn), methods=[method]))
    return Starlette(routes=app_routes)


def _collect_routes(instance: object) -> list[tuple[str, str, object, Callable[..., object]]]:
    seen: set[tuple[str, str]] = set()
    routes: list[tuple[str, str, object, Callable[..., object]]] = []
    for method, path, fn in routes_of(instance):
        key = (method, path)
        if key in seen:
            raise RouteRegistrationError(f"duplicate route: {method} {path}")
        seen.add(key)
        routes.append((method, path, instance, fn))
    return routes


def _make_endpoint(instance: object, fn: Callable[..., object]) -> Callable[[Request], Any]:
    async def endpoint(request: Request) -> Response:
        return await dispatch(instance, fn, request)

    return endpoint
