"""HTTP method decorators — ``@get``, ``@post``, ``@put``, ``@delete``, ``@patch``.

Also provides ``@router`` for grouping route methods under a URL prefix.

Decorated methods are discovered by :func:`_register_instance_routes` in
:mod:`~canary_framework.web.fastapi.web_canary` and registered with FastAPI
at startup time.

Each HTTP-method decorator accepts a path (relative to the router prefix)
and optional keyword arguments forwarded to ``FastAPI.add_api_route()``
(e.g. ``status_code``, ``response_model``, ``tags``).

Example::

    @router(prefix="/api/users")
    class UserRouter:
        def __init__(self, ctx: Context) -> None:
            self.user_service = ctx.resolve(UserService)

        @get("/")
        async def list_users(self) -> list[User]:
            return await self.user_service.list_all()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

_RT_ATTR = "__cf_router__"
_RT_PREFIX = "__cf_router_prefix__"
_RT_ROUTE = "__cf_route__"

_Fn = TypeVar("_Fn", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# @router
# ---------------------------------------------------------------------------


def router(
    prefix: str = "",
    deps: list[type] | None = None,
) -> Callable[[type], type]:
    """Mark a class as a route handler with an optional URL prefix and deps.

    Args:
        prefix: URL prefix prepended to every method path in this class.
            If ``""``, paths are registered as-is.
        deps: Reserved for future use (dependencies injected at route level).
    """
    _deps = list(deps or ())

    def decorator(cls: type) -> type:
        setattr(cls, _RT_ATTR, True)
        setattr(cls, _RT_PREFIX, prefix)
        cls.__cf_router_deps__ = _deps  # type: ignore[attr-defined]
        return cls

    return decorator


def is_router(cls: type) -> bool:
    """Return ``True`` if *cls* is decorated with ``@router``."""
    return bool(getattr(cls, _RT_ATTR, False))


def get_router_prefix(cls: type) -> str:
    """Return the URL prefix declared in ``@router(prefix=...)``."""
    return getattr(cls, _RT_PREFIX, "")


# ---------------------------------------------------------------------------
# HTTP method decorator factory
# ---------------------------------------------------------------------------


def _make_route(method: str) -> Callable[..., Any]:
    """Create a decorator for a specific HTTP method.

    The returned decorator is callable as ``@get("/path", **kwargs)``
    and stores metadata on the wrapped function as private attributes.

    Args:
        method: Uppercase HTTP method name (``"GET"``, ``"POST"``, …).
    """

    def decorator(path: str, **kwargs: Any) -> Callable[[_Fn], _Fn]:
        def inner(fn: _Fn) -> _Fn:
            setattr(fn, _RT_ROUTE, True)
            fn._cf_route_method_ = method  # type: ignore[attr-defined]
            fn._cf_route_path_ = path  # type: ignore[attr-defined]
            fn._cf_route_kwargs_ = kwargs  # type: ignore[attr-defined]
            return fn

        return inner

    return decorator


get = _make_route("GET")
"""``@get("/path")`` — register a GET handler."""

post = _make_route("POST")
"""``@post("/path", status_code=201)`` — register a POST handler."""

put = _make_route("PUT")
"""``@put("/path/{id}")`` — register a PUT handler."""

delete = _make_route("DELETE")
"""``@delete("/path/{id}")`` — register a DELETE handler."""

patch = _make_route("PATCH")
"""``@patch("/path/{id}")`` — register a PATCH handler."""


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def is_route_method(fn: Callable[..., Any]) -> bool:
    """Return ``True`` if *fn* was decorated with ``@get`` / ``@post`` / …"""
    return bool(getattr(fn, _RT_ROUTE, False))


def get_route_info(fn: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
    """Extract ``(method, path, kwargs)`` from a route-decorated function.

    Args:
        fn: A method decorated with ``@get``, ``@post``, etc.

    Returns:
        A 3-tuple of ``(HTTP_METHOD, path_string, extra_kwargs)``.
        Defaults to ``("GET", "/", {})`` if metadata is missing.
    """
    method = getattr(fn, "_cf_route_method_", "GET")
    path = getattr(fn, "_cf_route_path_", "/")
    kwargs = getattr(fn, "_cf_route_kwargs_", {})
    return method, path, kwargs
