"""HTTP route decorators — mark methods as request handlers.

路由装饰器：把 ``@cocoa`` 单元的方法标记为某个 HTTP 方法 + 路径的处理器。仿照
``core/decorator/decorators.py``——只 ``setattr`` 打标记、不改造类，因此方法仍是普通
方法，可以正常继承 / 混入。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from canary_framework.common.markers import ROUTE_ATTR

_T = TypeVar("_T", bound=Callable[..., object])


def route(method: str, path: str) -> Callable[[_T], _T]:
    """Mark *fn* as the handler for ``method path``.

    把方法标记为 ``method path`` 的处理器。``method`` 大小写不敏感，``path`` 若缺
    前缀斜杠会自动补齐。
    """
    method_ = method.upper()
    path_ = path if path.startswith("/") else "/" + path

    def mark(fn: _T) -> _T:
        setattr(fn, ROUTE_ATTR, (method_, path_))
        return fn

    return mark


def get(path: str) -> Callable[[_T], _T]:
    """``GET path``."""
    return route("GET", path)


def post(path: str) -> Callable[[_T], _T]:
    """``POST path``."""
    return route("POST", path)


def put(path: str) -> Callable[[_T], _T]:
    """``PUT path``."""
    return route("PUT", path)


def patch(path: str) -> Callable[[_T], _T]:
    """``PATCH path``."""
    return route("PATCH", path)


def delete(path: str) -> Callable[[_T], _T]:
    """``DELETE path``."""
    return route("DELETE", path)
