"""Web app builder — assemble route entries into a Starlette app.

app 构建：从单个或多个 ``@web_cocoa`` 单元收集 ``@get``/``@post`` 路由，组装成
Starlette 应用，并挂载 ``/openapi.json`` 与 ``/docs``。

异常有三条固定的出路，全部由框架内置、不可登记也不需要登记：请求绑定失败 → 422、
``HTTPError`` → 它自带的状态码、其余任何异常 → JSON 500。业务上"预期内的失败"该由
handler 自己以返回值表达（比如统一响应体里的 ``code``），而不是抛出去让框架翻译。

:func:`build_serve_app` 是 web 扩展交给运行时的**工厂**：``@web_cocoa`` 把它挂到
``SERVE_ATTR`` 标记下，``Canary`` 只按标记取出并调用，从不 import 本模块。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route as StarletteRoute

from canary_framework.common.markers import WEB_ATTR
from canary_framework.web.core.extension import _DEFAULT_TITLE, _DEFAULT_VERSION
from canary_framework.web.core.openapi import SWAGGER_UI_HTML, build_openapi
from canary_framework.web.core.routing import dispatch
from canary_framework.web.decorator.introspect import routes_of
from canary_framework.web.decorator.resolve import HandlerPlan, build_plan
from canary_framework.web.error.web import (
    HTTPError,
    RequestValidationError,
    RouteRegistrationError,
)


@dataclass(frozen=True, slots=True)
class Route:
    """One mounted route: which method + path, which unit's method, and its compiled plan.

    一条挂好的路由。``path`` 已含所在单元的 ``prefix``，``plan`` 是装配期编译好的取值
    计划——分发与文档都读它，两边因此不可能各推断出一套。
    """

    method: str
    path: str
    instance: object
    fn: Callable[..., object]
    plan: HandlerPlan


def build_serve_app(
    meta: dict[str, str],
    route_entries: list[Route],
) -> Starlette:
    """Build one Starlette app from pre-collected route entries, with a single OpenAPI doc.

    web 扩展交给运行时的工厂（挂在 ``SERVE_ATTR`` 下）：``route_entries`` 是所有
    ``@web_cocoa`` 单元按挂载前缀拼好完整路径后的路由条目，``meta`` 是最外层单元的
    ``WEB_ATTR``（提供 ``title`` / ``version``）。合并后只有一份 ``/docs`` 与
    ``/openapi.json``。
    """
    title = meta.get("title", _DEFAULT_TITLE)
    version = meta.get("version", _DEFAULT_VERSION)

    # 跨单元去重：同一 (method, path) 只能有一个处理器
    seen: dict[tuple[str, str], object] = {}
    for route in route_entries:
        key = (route.method, route.path)
        if key in seen:
            raise RouteRegistrationError(
                f"duplicate route: {route.method} {route.path} "
                f"({type(seen[key]).__name__} vs {type(route.instance).__name__})"
            )
        seen[key] = route.instance

    async def openapi_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(build_openapi(title, version, route_entries))

    async def docs_endpoint(request: Request) -> HTMLResponse:
        return HTMLResponse(SWAGGER_UI_HTML)

    app_routes: list[StarletteRoute] = [
        StarletteRoute("/openapi.json", openapi_endpoint, methods=["GET"]),
        StarletteRoute("/docs", docs_endpoint, methods=["GET"]),
    ]
    for route in route_entries:
        app_routes.append(StarletteRoute(route.path, _make_endpoint(route), methods=[route.method]))
    return Starlette(routes=app_routes, exception_handlers=_EXCEPTION_HANDLERS)


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


# 异常的三条固定出路。它们是**框架**层面的失败（请求根本没能进到 handler、或者 handler
# 炸了），不是业务失败——所以状态码就该是 4xx / 5xx，而不是包进业务信封里。
# Starlette 按 ``type(exc).__mro__`` 逐级向上查找，命中最具体的那一条。
_EXCEPTION_HANDLERS: dict[Any, Any] = {
    RequestValidationError: _handle_validation_error,
    HTTPError: _handle_http_error,
    Exception: _handle_server_error,
}


def collect_routes(declared: type, instance: object) -> list[Route]:
    """Collect ``(method, full path, instance, fn)`` for *instance*'s route-marked methods.

    路径在这里就拼完整：``prefix`` 是这个单元的**绝对**前缀，与它被谁依赖无关。依赖
    关系说的是启动顺序和谁能调用谁，URL 说的是对外的资源命名——两件事，不该互相决定。
    想要 ``/api/admin`` 就写 ``prefix="/api/admin"``。

    前缀取自 *declared*（图上登记的那个类型）而不是 ``type(instance)``：被 ``provide``
    顶掉的单元，替身身上没有 ``@web_cocoa`` 的标记，挂载点仍应由被替换者决定。
    """
    prefix: str = getattr(declared, WEB_ATTR, {}).get("prefix", "")
    seen: set[tuple[str, str]] = set()
    routes: list[Route] = []
    for method, path, fn in routes_of(instance):
        full = _join_path(prefix, path)
        key = (method, full)
        if key in seen:
            raise RouteRegistrationError(f"duplicate route: {method} {full}")
        seen.add(key)
        # 签名在这里编译一次，此后每个请求都不必再碰反射。
        routes.append(Route(method, full, instance, fn, build_plan(fn, full)))
    return routes


def _join_path(prefix: str, path: str) -> str:
    """Join a unit's *prefix* with a route-level *path*.

    路由自身的 ``/`` 要保留——``prefix="/api"`` 加上 ``@get("/")`` 得到 ``/api/``。
    """
    return prefix.rstrip("/") + path if prefix else path


def _make_endpoint(route: Route) -> Callable[[Request], Any]:
    """Close over everything the request path needs, so the request itself carries nothing.

    把实例、方法与编译好的计划闭包进去——请求到来时不再有任何查找。
    """

    async def endpoint(request: Request) -> Response:
        return await dispatch(route.instance, route.fn, route.plan, request)

    return endpoint
