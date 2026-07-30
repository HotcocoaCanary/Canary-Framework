"""Explicit service declaration decorator."""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import CF_NAME_ATTR, CF_SERVICE_MARKER, CF_SERVICE_META, ServiceMeta
from canary_framework.core.service import ServiceBase


def service() -> Callable[[type[ServiceBase]], type[ServiceBase]]:
    """Declare a lifecycle and dependency-injection service."""

    def decorate(cls: type[ServiceBase]) -> type[ServiceBase]:
        if not issubclass(cls, ServiceBase):
            raise TypeError(f"@service '{cls.__name__}' must inherit from ServiceBase.")
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, ServiceMeta(name=cls.__name__))
        setattr(cls, CF_NAME_ATTR, cls.__name__)
        return cls

    return decorate


__all__ = ["service"]
