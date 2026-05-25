"""Service decorator — marks a class as a Canary Framework service.

A **service** is the smallest runnable unit in the framework.  Services
declare a globally unique name, a list of dependency classes, and an
optional configuration class.  The framework discovers services via the
``@service`` decorator and manages their life-cycle (instantiation,
dependency injection, configuration loading, hook dispatch).

Type-safe metadata retrieval is provided by :func:`get_service_meta`,
which returns a :class:`ServiceMeta` :class:`~typing.TypedDict`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

_SERVICE_ATTR = "__cf_service__"
"""Set to ``True`` on classes decorated with ``@service``."""

_SERVICE_META = "__cf_service_meta__"
"""Stores a :class:`ServiceMeta` dict on decorated classes."""


class ServiceMeta(TypedDict, total=False):
    """Strongly-typed metadata stored on a ``@service``-decorated class.

    All keys are optional at the TypedDict level because the dict is
    constructed once when the decorator runs.  In practice ``name`` and
    ``deps`` are always present.
    """

    name: str
    """Globally unique service name used for dependency resolution."""

    deps: list[type]
    """List of ``@service`` / ``@module`` classes this service depends on."""

    config_cls: type | None
    """Optional ``@config``-decorated class.  ``None`` means the service
    inherits its parent module's configuration."""


def service(
    name: str,
    *,
    config: type | None = None,
    deps: list[type] | None = None,
) -> Callable[[type], type]:
    """Declare a class as a Canary Framework service.

    Args:
        name: Globally unique service name.  Used in ``deps=[]`` lists
            and for registry lookups.
        config: Optional ``@config``-decorated class providing typed
            settings for this service.
        deps: List of ``@service`` or ``@module`` classes that must be
            started before this service.  Each dependency instance is
            injected as ``self.<snake_case_name>`` in topological order.

    Raises:
        TypeError: (At decoration time, from ``@module``) if one of the
            ``deps`` entries is not a valid ``@service`` or ``@module``.

    Returns:
        A decorator that marks the class and attaches metadata.

    Example::

        @service(name="database", config=DBConfig)
        class DBService:
            @on_init
            def init(self, ctx: Context) -> None:
                cfg = ctx.config_as(DBConfig)
                self._pool = create_pool(cfg.dsn)
    """
    _config = config
    _deps = list(deps or ())

    def decorator(cls: type) -> type:
        meta: ServiceMeta = {
            "name": name,
            "deps": _deps,
            "config_cls": _config,
        }
        setattr(cls, _SERVICE_ATTR, True)
        setattr(cls, _SERVICE_META, meta)
        cls.__cf_name__ = name  # type: ignore[attr-defined]
        return cls

    return decorator


def is_cf_service(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@service``."""
    return bool(getattr(cls, _SERVICE_ATTR, False))


def get_service_meta(cls: type) -> ServiceMeta:
    """Return the :class:`ServiceMeta` dictionary attached by ``@service``.

    Returns an empty :class:`ServiceMeta` if the class was never decorated
    (all values default to their falsy equivalents).
    """
    raw: object = getattr(cls, _SERVICE_META, {})
    if isinstance(raw, dict):
        return raw  # type: ignore[return-value]
    return {}
