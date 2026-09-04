"""Declaration introspection — read back the ``@get`` / ``@on_request_error`` markers.

声明自省：读取路由与异常映射装饰器写下的标记，供扩展收集。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common.markers import ON_REQUEST_ERROR, ROUTE_ATTR


def routes_of(instance: object) -> list[tuple[str, str, Callable[..., object]]]:
    """Return ``(method, path, bound_method)`` for every route-marked method, base-first.

    仿照 :func:`canary_framework.core.decorator.introspect.hooks_of`：沿 MRO 基类优先
    扫描，混入的路由与本类路由都能注册（叠加而非覆盖）。
    """
    cls = type(instance)
    routes: list[tuple[str, str, Callable[..., object]]] = []
    seen: set[Callable[..., object]] = set()
    for klass in reversed(cls.__mro__):  # 基类 → 派生类
        for raw in klass.__dict__.values():
            if not callable(raw) or not hasattr(raw, ROUTE_ATTR):
                continue
            if raw in seen:
                continue
            seen.add(raw)
            method, path = getattr(raw, ROUTE_ATTR)
            routes.append((method, path, raw.__get__(instance, klass)))
    return routes


def error_handlers_of(instance: object) -> list[tuple[type[Exception], Callable[..., object]]]:
    """Return ``(exc_type, bound_method)`` for every ``@on_request_error`` method, base-first.

    与 :func:`routes_of` 同构：沿 MRO 基类优先扫描，混入的映射与本类映射都生效。
    一个方法登记多个异常类型时，展开成多条。
    """
    cls = type(instance)
    handlers: list[tuple[type[Exception], Callable[..., object]]] = []
    seen: set[Callable[..., object]] = set()
    for klass in reversed(cls.__mro__):  # 基类 → 派生类
        for raw in klass.__dict__.values():
            if not callable(raw) or not hasattr(raw, ON_REQUEST_ERROR):
                continue
            if raw in seen:
                continue
            seen.add(raw)
            bound = raw.__get__(instance, klass)
            handlers.extend((exc_type, bound) for exc_type in getattr(raw, ON_REQUEST_ERROR))
    return handlers
