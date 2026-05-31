""""@module" decorator."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import (
    CF_MODULE_MARKER,
    ModuleMeta,
    is_cf_service,
)
from canary_framework.core import ModuleBase
from canary_framework.decorators.service import _make_subclass


def module(
    name: str,
    *,
    deps: list[type] | None = None,
    services: list[type] | None = None,
    config: type | None = None,
) -> Callable[[type], type[ModuleBase]]:
    """Declare a class as a Canary Framework module.

    Args:
        name: Globally unique module name.
        deps: Dependency classes.
        services: Direct child nodes.
        config: Optional per-module config class.

    Raises:
        TypeError: If any service in ``services`` is not decorated.
    """
    _deps = list(deps or ())
    _services = list(services or ())

    def decorator(cls: type) -> type[ModuleBase]:
        for svc_cls in _services:
            if not is_cf_service(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' "
                    f"is not decorated with @service or @module."
                )

        meta = ModuleMeta(
            name=name,
            deps=_deps,
            services=_services,
            config_cls=config,
        )

        return cast(
            type[ModuleBase],
            _make_subclass(cls, ModuleBase, meta, name, extra_marker=CF_MODULE_MARKER),
        )

    return decorator


__all__ = ["module"]
