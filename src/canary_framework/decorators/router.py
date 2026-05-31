""""@router" decorator and HTTP method decorators."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import (
    CF_ROUTER_MARKER,
    ROUTE_ATTR,
    HookFunction,
    RouterMeta,
)
from canary_framework.core import RouterBase
from canary_framework.decorators.service import _make_subclass


def _http_method(method: str, path: str) -> Callable[[HookFunction], HookFunction]:
    def decorator(fn: HookFunction) -> HookFunction:
        setattr(fn, ROUTE_ATTR, {"method": method, "path": path})
        return fn

    return decorator


def get(path: str) -> Callable[[HookFunction], HookFunction]:
    """Mark an async method as a GET route handler."""
    return _http_method("GET", path)


def post(path: str) -> Callable[[HookFunction], HookFunction]:
    """Mark an async method as a POST route handler."""
    return _http_method("POST", path)


def put(path: str) -> Callable[[HookFunction], HookFunction]:
    """Mark an async method as a PUT route handler."""
    return _http_method("PUT", path)


def delete(path: str) -> Callable[[HookFunction], HookFunction]:
    """Mark an async method as a DELETE route handler."""
    return _http_method("DELETE", path)


def patch(path: str) -> Callable[[HookFunction], HookFunction]:
    """Mark an async method as a PATCH route handler."""
    return _http_method("PATCH", path)


def router(
    prefix: str = "",
    *,
    name: str = "",
    deps: list[type] | None = None,
    tags: list[str] | None = None,
) -> Callable[[type], type[RouterBase]]:
    """Declare a class as a Canary Framework router service.

    Combines ``@service`` semantics with HTTP route grouping.

    Args:
        prefix: URL prefix applied to all routes in this group.
        name: Globally unique service name.
        deps: Dependency classes.
        tags: OpenAPI tags for this route group.
    """
    _deps = list(deps or ())
    _tags = list(tags or [])

    def decorator(cls: type) -> type[RouterBase]:
        routes: list[HookFunction] = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if callable(attr) and hasattr(attr, ROUTE_ATTR):
                routes.append(attr)

        meta = RouterMeta(
            name=name or cls.__name__.lower(),
            deps=_deps,
            prefix=prefix,
            tags=_tags,
            routes=routes,
        )

        return cast(
            type[RouterBase],
            _make_subclass(
                cls, RouterBase, meta, meta.name, extra_marker=CF_ROUTER_MARKER
            ),
        )

    return decorator


__all__ = [
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "router",
]
