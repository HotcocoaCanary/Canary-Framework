"""Module decorator — marks a class as a composable group of services.

A **module** is itself a service (it supports configuration and lifecycle
hooks), with the additional ability to declare child services via the
``services`` parameter.  Modules form a tree whose root is passed to
:class:`~canary_framework.core.engine.canary.Canary` at startup.

Configuration inheritance:
    When a child service does not declare its own ``config``, it inherits
    the configuration class of its parent module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from canary_framework.core.decorators.service import is_cf_service

_MODULE_ATTR = "_cf_module__"
"""Set to ``True`` on classes decorated with ``@module``."""

_MODULE_META = "_cf_module_meta__"
"""Stores a :class:`ModuleMeta` dict on decorated classes."""


class ModuleMeta(TypedDict, total=False):
    """Strongly-typed metadata stored on a ``@module``-decorated class."""

    name: str
    """Globally unique module name."""

    config_cls: type | None
    """Optional ``@config``-decorated class shared by child services."""

    services: list[type]
    """List of ``@service`` / ``@module`` classes that belong to this module."""


def module(
    name: str,
    *,
    config: type | None = None,
    services: list[type] | None = None,
) -> Callable[[type], type]:
    """Declare a class as a Canary Framework module.

    Args:
        name: Globally unique module name.  Serves as a namespace for
            child services and an identifier for dependency resolution.
        config: Optional ``@config``-decorated class.  Child services
            that do not declare their own ``config`` inherit this one.
        services: List of ``@service`` or ``@module``-decorated classes
            that are direct children of this module.

    Raises:
        TypeError: (At decoration time) if any entry in *services* is
            not a valid ``@service`` or ``@module`` class.

    Returns:
        A decorator that marks the class and attaches metadata.

    Example::

        @module(name="AppModule", config=AppConfig, services=[DBService, UserService])
        class AppModule:
            pass
    """
    _config = config
    _services = list(services or ())

    def decorator(cls: type) -> type:
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not "
                    f"decorated with @service or @module. "
                    f"All entries in the 'services' list must be framework classes."
                )

        meta: ModuleMeta = {
            "name": name,
            "config_cls": _config,
            "services": _services,
        }
        setattr(cls, _MODULE_ATTR, True)
        setattr(cls, _MODULE_META, meta)
        cls.__cf_name__ = name  # type: ignore[attr-defined]
        return cls

    return decorator


def is_cf_module(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@module``."""
    return bool(getattr(cls, _MODULE_ATTR, False))


def get_module_meta(cls: type) -> ModuleMeta:
    """Return the :class:`ModuleMeta` dictionary attached by ``@module``.

    Returns an empty :class:`ModuleMeta` if the class was never decorated.
    """
    raw: object = getattr(cls, _MODULE_META, {})
    if isinstance(raw, dict):
        return raw  # type: ignore[return-value]
    return {}
