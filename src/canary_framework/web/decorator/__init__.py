"""Declarations — route decorators and parameter markers, plus their introspection.

声明层：``@get``/``@post`` 等路由装饰器与 ``Query``/``Path`` 等参数标记，及其自省工具。
只打标记、不改造类；运行时读取标记来分发请求与生成文档。
"""

from canary_framework.web.decorator.introspect import routes_of
from canary_framework.web.decorator.params import Body, Cookie, Header, Param, Path, Query
from canary_framework.web.decorator.resolve import (
    hints_of,
    location_of,
    path_param_names,
    resolve_meta,
    unwrap,
)
from canary_framework.web.decorator.routes import delete, get, patch, post, put, route

__all__ = [
    "Body",
    "Cookie",
    "Header",
    "Param",
    "Path",
    "Query",
    "delete",
    "get",
    "hints_of",
    "location_of",
    "patch",
    "path_param_names",
    "post",
    "put",
    "resolve_meta",
    "route",
    "routes_of",
    "unwrap",
]
