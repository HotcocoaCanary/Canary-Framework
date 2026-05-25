"""``@web`` decorator — marks a service/module as a Web endpoint.

Declares which ``@router`` classes handle HTTP routing for this
service or module.  The relationship between ``@web`` and ``@router``:

    ``@web(routers=[UserRouter])``  — declares the routers used
    ``@router(prefix="/api")``     — groups route methods under a prefix

Routing rules (applied by :func:`_register_routes`):
    1. Has ``routers=[]`` → registers the methods of each ``@router`` class.
    2. No routers + ``@module`` / ``@service`` → registers any ``@get`` /
       ``@post`` methods defined directly on the class.
    3. Has ``routers=[]`` + ``@module`` → registers both.
"""

from __future__ import annotations

from collections.abc import Callable

_WEB_ATTR = "__cf_web__"
"""Set to ``True`` on classes decorated with ``@web``."""

_WEB_ROUTERS = "__cf_web_routers__"
"""Stores the list of ``@router``-decorated classes."""


def web(routers: list[type] | None = None) -> Callable[[type], type]:
    """Mark a service or module as a Web endpoint.

    Args:
        routers: A list of ``@router``-decorated classes whose HTTP
            methods should be registered with FastAPI.

    Returns:
        A class decorator.

    Example::

        @web(routers=[UserRouter, HealthRouter])
        @module(name="AppModule", services=[UserService])
        class AppModule:
            @get("/health")
            async def health(self) -> dict:
                return {"status": "ok"}
    """
    _routers = list(routers or ())

    def decorator(cls: type) -> type:
        setattr(cls, _WEB_ATTR, True)
        setattr(cls, _WEB_ROUTERS, _routers)
        return cls

    return decorator


def is_web(cls: type) -> bool:
    """Return ``True`` if *cls* is decorated with ``@web``."""
    return bool(getattr(cls, _WEB_ATTR, False))


def get_web_routers(cls: type) -> list[type]:
    """Return the list of ``@router`` classes declared via ``@web(routers=[...])``."""
    return getattr(cls, _WEB_ROUTERS, [])
