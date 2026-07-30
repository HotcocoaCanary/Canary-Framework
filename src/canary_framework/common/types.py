"""Framework-wide shared enums, type aliases, and data classes.

该模块具有零框架内部依赖，可以安全地被所有其他模块导入。

Has zero framework-internal dependencies — safe for all other modules to import.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import UnionType
from typing import Any, Protocol, get_args, get_origin

from canary_framework.common.config import CanaryConfig


class LifecycleState(StrEnum):
    """Runtime lifecycle states for service nodes."""

    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    FAILED = "failed"


class LifecycleAware(Protocol):
    """生命周期感知接口。"""

    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...


def unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """从 Optional[T] 或 T | None 中提取内部类型 T。

    支持 typing.Optional (typing.Union[T, None]) 和 Python 3.10+ 的 T | None。
    返回 (inner_type, is_nullable)。

    Extract inner type from Optional[T] or T | None.

    Supports both typing.Optional and T | None syntax.
    Returns (inner_type, is_nullable).
    """
    import typing as _typing

    origin = get_origin(tp)
    if origin is UnionType or origin is _typing.Union:
        args = get_args(tp)
        inner = [a for a in args if a is not type(None)]
        if len(inner) == 1:
            return inner[0], True
    return tp, False


@dataclass(frozen=True, slots=True)
class ServiceMeta:
    """Immutable metadata for a service declaration."""

    name: str


@dataclass(frozen=True, slots=True)
class RouterMeta(ServiceMeta):
    """Immutable metadata for a router node."""

    prefix: str = ""
    tags: tuple[str, ...] = ()
    security: tuple[str, ...] = ()
    config_cls: type[CanaryConfig] | None = None


@dataclass(frozen=True, slots=True)
class ModuleMeta(ServiceMeta):
    """Immutable metadata for a module node."""

    children: tuple[type, ...] = ()
    prefix: str = ""
    tags: tuple[str, ...] = ()
    security: tuple[str, ...] = ()
    config_cls: type[CanaryConfig] | None = None


@dataclass(slots=True)
class ServiceEntry:
    """Mutable runtime record for a service instance."""

    cls: type
    name: str
    instance: object | None = None


# Service标记常量
# Service marker constants
CF_SERVICE_MARKER = "__cf_service__"
CF_SERVICE_META = "__cf_service_meta__"

# 名称属性常量
# Name attribute constant
CF_NAME_ATTR = "__cf_name__"


def is_cf_service(cls: type) -> bool:
    """检查类是否被@service装饰器装饰。

    Args:
        cls: 要检查的类。

    Returns:
        如果类被@service装饰器装饰，则返回True；否则返回False。

    Check if a class is decorated with @service.

    Args:
        cls: The class to check.

    Returns:
        True if the class is decorated with @service, False otherwise.
    """
    return bool(getattr(cls, CF_SERVICE_MARKER, False))


def is_cf_router(cls: type) -> bool:
    """Check whether a class is a router node."""

    return isinstance(getattr(cls, CF_SERVICE_META, None), RouterMeta)


def get_service_meta(cls: type) -> ServiceMeta | None:
    """Get service-node metadata."""

    raw = getattr(cls, CF_SERVICE_META, None)
    return raw if isinstance(raw, ServiceMeta) else None


def get_router_meta(cls: type) -> RouterMeta | None:
    """Get router-node metadata."""

    raw = getattr(cls, CF_SERVICE_META, None)
    return raw if isinstance(raw, RouterMeta) else None


def is_cf_module(cls: type) -> bool:
    """检查类是否被@module装饰器装饰。

    Args:
        cls: 要检查的类。

    Returns:
        如果类被@module装饰器装饰，则返回True；否则返回False。

    Check if a class is decorated with @module.

    Args:
        cls: The class to check.

    Returns:
        True if the class is decorated with @module, False otherwise.
    """
    return isinstance(getattr(cls, CF_SERVICE_META, None), ModuleMeta)


def get_module_meta(cls: type) -> ModuleMeta | None:
    """获取模块类的元数据。

    Args:
        cls: 模块类。

    Returns:
        ModuleMeta对象，如果不存在则返回None。

    Get metadata for a module class.

    Args:
        cls: The module class.

    Returns:
        ModuleMeta object, or None if not found.
    """
    raw = getattr(cls, CF_SERVICE_META, None)
    if isinstance(raw, ModuleMeta):
        return raw
    return None


__all__ = [
    "CF_NAME_ATTR",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "LifecycleAware",
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
