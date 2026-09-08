"""Declaration introspection — read back the ``@get`` / ``@post`` markers.

声明自省：读取路由装饰器写下的标记，供 web 扩展收集。

扫描本身不在这里——它和生命周期钩子的扫描是同一件事，收口在
:func:`canary_framework.core.decorator.introspect.marked_members`。这里只负责把载荷
摊开成调用方要的形状。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common.markers import ROUTE_ATTR
from canary_framework.core.decorator.introspect import marked_members
from canary_framework.web.decorator.routes import RouteMark


def routes_of(instance: object) -> list[tuple[RouteMark, Callable[..., object]]]:
    """Return ``(mark, bound method)`` for every route-marked method, base-first.

    返回该实例上所有被路由标记过的方法，基类在前——混入（mixin）带来的路由与本类自己
    的路由都会注册，两者叠加而非互相覆盖。
    """
    return [(mark, fn) for mark, fn in marked_members(instance, ROUTE_ATTR)]
