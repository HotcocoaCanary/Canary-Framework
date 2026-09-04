"""Web app builder — assemble route entries into a Starlette app.

app 构建：从单个或多个 ``@web_cocoa`` 单元收集 ``@get``/``@post`` 路由与
``@on_request_error`` 异常映射，组装成 Starlette 应用，并挂载 ``/openapi.json``、
``/docs``、``/redoc``。

:func:`build_serve_app` 是 web 扩展交给运行时的**工厂**：``@web_cocoa`` 把它挂到
``SERVE_ATTR`` 标记下，``Canary`` 只按标记取出并调用，从不 import 本模块。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from canary_framework.common.markers import WEB_ATTR
from canary_framework.runtime.mounts import join_path
from canary_framework.web.core.openapi import REDOC_HTML, SWAGGER_UI_HTML, build_openapi
from canary_framework.web.core.routing import dispatch
from canary_framework.web.decorator.introspect import error_handlers_of, routes_of
from canary_framework.web.error.web import (
    HTTPError,
    RequestValidationError,
    RouteRegistrationError,
)

_ErrorEntry = tuple[type[Exception], Callable[..., object]]

_DEFAULT_TITLE = "Canary API"
_DEFAULT_VERSION = "0.1.0"


def build_web_app(instance: object) -> Starlette:
    """Collect *instance*'s routes and build a Starlette app plus its OpenAPI doc.

    单元自建应用的快捷方式（不含嵌套）：只挂 *instance* 自己的路由，前缀取它的
    ``prefix``。整图合并由 ``Canary`` 通过 :func:`build_serve_app` 完成。
    """
    meta: dict[str, str] = getattr(type(instance), WEB_ATTR, {})
    prefix = meta.get("prefix", "")
    routes = [(m, join_path(prefix, p), inst, fn) for m, p, inst, fn in collect_routes(instance)]
    return build_serve_app(meta, routes, collect_error_handlers(instance))


def build_serve_app(
    meta: dict[str, str],
    route_entries: list[tuple[str, str, object, Callable[..., object]]],
    error_entries: list[_ErrorEntry] | None = None,
) -> Starlette:
    """Build one Starlette app from pre-collected route entries, with a single OpenAPI doc.

    web 扩展交给运行时的工厂（挂在 ``SERVE_ATTR`` 下）：``route_entries`` 是所有
    ``@web_cocoa`` 单元按挂载前缀拼好完整路径后的路由条目，``meta`` 是最外层单元的
    ``WEB_ATTR``（提供 ``title`` / ``version``）。合并后只有一份 ``/docs`` 与
    ``/openapi.json``。``error_entries`` 是所有单元的 ``@on_request_error`` 登记，
    作用域为全应用。
    """
    title = meta.get("title", _DEFAULT_TITLE)
    version = meta.get("version", _DEFAULT_VERSION)

    # 跨实例、跨挂载点去重：同一 (method, path) 只能有一个处理器
    seen: dict[tuple[str, str], object] = {}
    deduped: list[tuple[str, str, object, Callable[..., object]]] = []
    for method, path, instance, fn in route_entries:
        key = (method, path)
        if key in seen:
            raise RouteRegistrationError(
                f"duplicate route: {method} {path} "
                f"({type(seen[key]).__name__} vs {type(instance).__name__})"
            )
        seen[key] = instance
        deduped.append((method, path, instance, fn))

    async def openapi_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(build_openapi(title, version, deduped))

    async def docs_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(SWAGGER_UI_HTML)

    async def redoc_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(REDOC_HTML)

    app_routes: list[Route] = [
        Route("/openapi.json", openapi_endpoint, methods=["GET"]),
        Route("/docs", docs_endpoint, methods=["GET"]),
        Route("/redoc", redoc_endpoint, methods=["GET"]),
    ]
    for method, path, instance, fn in deduped:
        app_routes.append(Route(path, _make_endpoint(instance, fn), methods=[method]))
    return Starlette(routes=app_routes, exception_handlers=_exception_handlers(error_entries or []))


def _exception_handlers(error_entries: list[_ErrorEntry]) -> dict[Any, Any]:
    """Merge the built-in mappings with the units' ``@on_request_error`` registrations.

    内置三条兜底（422 / ``HTTPError`` / 500）先铺上，使用者的登记再覆盖上去——覆盖
    内置是有意支持的（换成自家错误信封）；使用者之间重复登记同一类型则报错。
    """
    handlers: dict[Any, Any] = {
        RequestValidationError: _handle_validation_error,
        HTTPError: _handle_http_error,
        Exception: _handle_server_error,
    }
    registered: dict[type[Exception], Callable[..., object]] = {}
    for exc_type, fn in error_entries:
        if exc_type in registered:
            raise RouteRegistrationError(
                f"duplicate @on_request_error for {exc_type.__name__}: "
                f"{_where(registered[exc_type])} vs {_where(fn)}"
            )
        registered[exc_type] = fn
        handlers[exc_type] = _make_error_endpoint(fn)
    return handlers


def _where(fn: Callable[..., object]) -> str:
    return getattr(fn, "__qualname__", repr(fn))


def _make_error_endpoint(fn: Callable[..., object]) -> Callable[[Request, Exception], Any]:
    async def endpoint(request: Request, exc: Exception) -> Response:
        return cast(Response, await cast(Any, fn)(request, exc))

    return endpoint


async def _handle_validation_error(request: Request, exc: Exception) -> Response:
    return JSONResponse({"detail": cast(RequestValidationError, exc).detail}, status_code=422)


async def _handle_http_error(request: Request, exc: Exception) -> Response:
    error = cast(HTTPError, exc)
    return JSONResponse(
        {"detail": error.detail}, status_code=error.status_code, headers=error.headers
    )


async def _handle_server_error(request: Request, exc: Exception) -> Response:
    # 兜底成 JSON（Starlette 默认是 text/plain）；ServerErrorMiddleware 随后仍会重新
    # 抛出，因此 traceback 照常进服务器日志。
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


def collect_routes(
    instance: object,
) -> list[tuple[str, str, object, Callable[..., object]]]:
    """Collect ``(method, path, instance, fn)`` tuples for *instance*'s route-marked methods.

    供 ``@web_cocoa`` 的 ``@on_start`` 钩子调用，也供 ``_collect_serve_app``
    在多单元合并时使用。
    """
    seen: set[tuple[str, str]] = set()
    routes: list[tuple[str, str, object, Callable[..., object]]] = []
    for method, path, fn in routes_of(instance):
        key = (method, path)
        if key in seen:
            raise RouteRegistrationError(f"duplicate route: {method} {path}")
        seen.add(key)
        routes.append((method, path, instance, fn))
    return routes


def collect_error_handlers(instance: object) -> list[_ErrorEntry]:
    """Collect ``(exc_type, bound_method)`` for *instance*'s ``@on_request_error`` methods.

    与 :func:`collect_routes` 对称，供 ``@web_cocoa`` 的启动钩子调用。
    """
    return error_handlers_of(instance)


def _make_endpoint(instance: object, fn: Callable[..., object]) -> Callable[[Request], Any]:
    async def endpoint(request: Request) -> Response:
        return await dispatch(instance, fn, request)

    return endpoint
