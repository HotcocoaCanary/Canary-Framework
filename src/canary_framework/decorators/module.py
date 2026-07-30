"""Explicit module declaration decorator."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    CanaryConfig,
    ModuleMeta,
    is_cf_service,
)
from canary_framework.core.module import ModuleBase
from canary_framework.decorators.router import _HANDLER_ROUTE_SPECS_ATTR


def module(
    *,
    children: Sequence[type] = (),
    prefix: str = "",
    tags: Sequence[str] = (),
    security: Sequence[str] = (),
    config: type[CanaryConfig] | None = None,
) -> Callable[[type[ModuleBase]], type[ModuleBase]]:
    """Declare a Module with explicit children and inherited route context."""
    child_types = tuple(children)
    for child in child_types:
        if isinstance(child, type) and issubclass(child, CanaryConfig):
            raise TypeError(f"Config {child.__name__} cannot be a Module child.")
        if not is_cf_service(child):
            raise TypeError(f"Module child {child!r} must be decorated by Canary Framework.")
    if config is not None and not issubclass(config, CanaryConfig):
        raise TypeError("module config must inherit from CanaryConfig.")

    def decorate(cls: type[ModuleBase]) -> type[ModuleBase]:
        if not issubclass(cls, ModuleBase):
            raise TypeError(f"@module '{cls.__name__}' must inherit from ModuleBase.")
        for value in cls.__dict__.values():
            if getattr(value, _HANDLER_ROUTE_SPECS_ATTR, ()):
                raise TypeError(f"Module {cls.__name__} may not declare business routes.")
        meta = ModuleMeta(
            name=cls.__name__,
            children=child_types,
            prefix=prefix,
            tags=tuple(tags),
            security=tuple(security),
            config_cls=config,
        )
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, meta)
        setattr(cls, CF_NAME_ATTR, cls.__name__)
        return cls

    return decorate


__all__ = ["module"]
