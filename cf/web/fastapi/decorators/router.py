from __future__ import annotations

from typing import Any, Callable

_CF_ROUTER_ATTR   = "__cf_router__"
_CF_ROUTER_PREFIX = "__cf_router_prefix__"
_CF_ROUTE_ATTR    = "__cf_route__"


def router(prefix: str = "", deps: list[type] | None = None):
    _deps = deps or []

    def decorator(cls: type) -> type:
        setattr(cls, _CF_ROUTER_ATTR, True)
        setattr(cls, _CF_ROUTER_PREFIX, prefix)
        setattr(cls, "__cf_router_deps__", _deps)
        return cls

    return decorator


def is_router(cls: type) -> bool:
    return bool(getattr(cls, _CF_ROUTER_ATTR, False))


def get_router_prefix(cls: type) -> str:
    return getattr(cls, _CF_ROUTER_PREFIX, "")


def _make_route(method: str):
    def decorator(path: str, **kwargs: Any):
        def inner(fn: Callable[..., Any]) -> Callable[..., Any]:
            setattr(fn, _CF_ROUTE_ATTR, True)
            setattr(fn, "_cf_route_method_", method)
            setattr(fn, "_cf_route_path_", path)
            setattr(fn, "_cf_route_kwargs_", kwargs)
            return fn
        return inner
    return decorator


get    = _make_route("GET")
post   = _make_route("POST")
put    = _make_route("PUT")
delete = _make_route("DELETE")
patch  = _make_route("PATCH")


def is_route_method(fn: Callable[..., Any]) -> bool:
    return bool(getattr(fn, _CF_ROUTE_ATTR, False))


def get_route_info(fn: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
    method = getattr(fn, "_cf_route_method_", "GET")
    path   = getattr(fn, "_cf_route_path_", "/")
    kwargs = getattr(fn, "_cf_route_kwargs_", {})
    return method, path, kwargs
