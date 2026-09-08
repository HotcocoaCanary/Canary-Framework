"""Declarations — route decorators and parameter markers, plus their introspection.

声明层：``@get``/``@post`` 等路由装饰器与 ``Header``/``Cookie`` 参数标记，及其自省
工具。只打标记、不改造类；运行时读取标记来分发请求与生成文档。
"""

from canary_framework.web.decorator.introspect import routes_of
from canary_framework.web.decorator.params import Cookie, Header, Param
from canary_framework.web.decorator.resolve import (
    hints_of,
    location_of,
    path_param_names,
    unwrap,
)
from canary_framework.web.decorator.routes import delete, get, patch, post, put, route

__all__ = [
    "Cookie",
    "Header",
    "Param",
    "delete",
    "get",
    "hints_of",
    "location_of",
    "patch",
    "path_param_names",
    "post",
    "put",
    "route",
    "routes_of",
    "unwrap",
]
