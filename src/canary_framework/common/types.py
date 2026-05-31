"""Framework-wide shared enums, type aliases, and data classes.

Has zero framework-internal dependencies — safe for all other modules to import.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class LifecycleHook(StrEnum):
    """Lifecycle phases for hook registration."""

    AFTER_CONFIG = "after_config"
    AFTER_INIT = "after_init"
    BEFORE_STARTUP = "before_startup"
    BEFORE_SHUTDOWN = "before_shutdown"


HookFunction = Callable[..., object]


@dataclass(slots=True)
class ServiceMeta:
    """Metadata stored on a ``@service``-decorated class."""

    name: str
    deps: list[type] = field(default_factory=list)


@dataclass(slots=True)
class ModuleMeta(ServiceMeta):
    """Metadata stored on a ``@module``-decorated class."""

    services: list[type] = field(default_factory=list)
    config_cls: type | None = field(default=None)


@dataclass(slots=True)
class RouterMeta(ServiceMeta):
    """Metadata stored on a ``@router``-decorated class."""

    prefix: str = ""
    tags: list[str] = field(default_factory=list)
    routes: list[HookFunction] = field(default_factory=list)


@dataclass(slots=True)
class ServiceEntry:
    """Runtime descriptor for a single ``@service`` or ``@module`` instance."""

    cls: type
    name: str
    instance: object | None = field(default=None)
    deps: list[type] = field(default_factory=list)
    dep_names: list[str] = field(default_factory=list)


__all__ = [
    "HookFunction",
    "LifecycleHook",
    "ModuleMeta",
    "RouterMeta",
    "ServiceEntry",
    "ServiceMeta",
]
