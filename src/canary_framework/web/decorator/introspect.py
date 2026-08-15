"""Route introspection — read back the ``@get``/``@post`` markers.

路由自省：读取路由装饰器写下的标记，供扩展收集路由。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common.markers import ROUTE_ATTR


def routes_of(instance: object) -> list[tuple[str, str, Callable[..., object]]]:
    """Return ``(method, path, bound_method)`` for every route-marked method, base-first.

    仿照 :func:`canary_framework.core.decorator.introspect.hooks_of`：沿 MRO 基类优先
    扫描，混入的路由与本类路由都能注册（叠加而非覆盖）。
    """
    cls = type(instance)
    routes: list[tuple[str, str, Callable[..., object]]] = []
    seen: set[str] = set()
    for klass in reversed(cls.__mro__):  # 基类 → 派生类
        for name in klass.__dict__:
            if name in seen:
                continue
            seen.add(name)
            fn = getattr(instance, name, None)
            if callable(fn) and hasattr(fn, ROUTE_ATTR):
                method, path = getattr(fn, ROUTE_ATTR)
                routes.append((method, path, fn))
    return routes
