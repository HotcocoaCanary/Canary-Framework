"""Canary web extension — ASGI apps over ``@cocoa`` services.

web 扩展：基于 Starlette + Pydantic，把 ``@cocoa`` 服务暴露为 ASGI 应用。用
``@web_cocoa`` 标记单元、``@get``/``@post`` 标记路由方法，``Canary(...)`` 收集路由、
自动注入参数并生成 OpenAPI 文档（``/docs`` / ``/redoc`` / ``/openapi.json``）。

依赖 ``canary-framework[web]``：starlette + pydantic + uvicorn。
"""

from __future__ import annotations

from canary_framework.web.core.extension import web_cocoa
from canary_framework.web.decorator.params import Body, Cookie, Header, Path, Query
from canary_framework.web.decorator.routes import delete, get, patch, post, put, route
from canary_framework.web.error.web import (
    MissingParameterError,
    RouteRegistrationError,
    WebError,
)

__all__ = [
    "Body",
    "Cookie",
    "Header",
    "MissingParameterError",
    "Path",
    "Query",
    "RouteRegistrationError",
    "WebError",
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "route",
    "web_cocoa",
]
