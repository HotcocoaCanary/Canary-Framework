"""Framework-wide enums, protocols, metadata, and marker helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import UnionType
from typing import Any, Union, get_args, get_origin

from canary_framework.common.config import CanaryConfig


class LifecycleState(StrEnum):
    """Represent the public lifecycle state of a runtime node."""

    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    FAILED = "failed"


def unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """Return the non-None type and whether the input was optional."""
    origin = get_origin(tp)
    if origin is UnionType or origin is Union:
        args = get_args(tp)
        inner = [a for a in args if a is not type(None)]
        if len(inner) == 1:
            return inner[0], True
    return tp, False


@dataclass(frozen=True, slots=True)
class ServiceMeta:
    """Describe a declared service node."""

    name: str


@dataclass(frozen=True, slots=True)
class RouterMeta(ServiceMeta):
    """Describe a declared Router and its route context."""

    prefix: str = ""
    tags: tuple[str, ...] = ()
    security: tuple[str, ...] = ()
    config_cls: type[CanaryConfig] | None = None


@dataclass(frozen=True, slots=True)
class ModuleMeta(ServiceMeta):
    """Describe a declared Module and its children."""

    children: tuple[type, ...] = ()
    prefix: str = ""
    tags: tuple[str, ...] = ()
    security: tuple[str, ...] = ()
    config_cls: type[CanaryConfig] | None = None


@dataclass(slots=True)
class ServiceEntry:
    """Store one registered service class and optional instance."""

    cls: type
    name: str
    instance: object | None = None


CF_SERVICE_MARKER = "__cf_service__"
CF_SERVICE_META = "__cf_service_meta__"
CF_NAME_ATTR = "__cf_name__"


def is_cf_service(cls: type) -> bool:
    return bool(getattr(cls, CF_SERVICE_MARKER, False))


def is_cf_router(cls: type) -> bool:
    return isinstance(getattr(cls, CF_SERVICE_META, None), RouterMeta)


def get_service_meta(cls: type) -> ServiceMeta | None:
    return raw if isinstance(raw := getattr(cls, CF_SERVICE_META, None), ServiceMeta) else None


def get_router_meta(cls: type) -> RouterMeta | None:
    return raw if isinstance(raw := getattr(cls, CF_SERVICE_META, None), RouterMeta) else None


def is_cf_module(cls: type) -> bool:
    return isinstance(getattr(cls, CF_SERVICE_META, None), ModuleMeta)


def get_module_meta(cls: type) -> ModuleMeta | None:
    return raw if isinstance(raw := getattr(cls, CF_SERVICE_META, None), ModuleMeta) else None


__all__ = [
    "CF_NAME_ATTR",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "LifecycleState",
    "ModuleMeta",
    "RouterMeta",
    "ServiceEntry",
    "ServiceMeta",
    "get_module_meta",
    "get_router_meta",
    "get_service_meta",
    "is_cf_module",
    "is_cf_router",
    "is_cf_service",
    "unwrap_optional",
]
