"""Dynamic subclass factory and ``@service`` decorator."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ServiceMeta,
)
from canary_framework.core import ServiceBase


def _make_subclass(
    cls: type,
    base: type,
    meta: ServiceMeta,
    name: str,
    *,
    extra_marker: str | None = None,
) -> type:
    new_cls = type(cls.__name__, (base, cls), {})
    new_cls.__module__ = cls.__module__
    new_cls.__qualname__ = cls.__qualname__
    setattr(new_cls, CF_SERVICE_MARKER, True)
    setattr(new_cls, CF_SERVICE_META, meta)
    setattr(new_cls, CF_NAME_ATTR, name)
    if extra_marker is not None:
        setattr(new_cls, extra_marker, True)
    return new_cls


def service(
    name: str,
    *,
    deps: list[type] | None = None,
) -> Callable[[type], type[ServiceBase]]:
    """Declare a class as a Canary Framework service.

    Args:
        name: Globally unique service name.
        deps: Dependency classes injected as snake_case attributes.
    """
    _deps = list(deps or ())

    def decorator(cls: type) -> type[ServiceBase]:
        meta = ServiceMeta(name=name, deps=_deps)
        return cast(type[ServiceBase], _make_subclass(cls, ServiceBase, meta, name))

    return decorator


__all__ = ["_make_subclass", "service"]
