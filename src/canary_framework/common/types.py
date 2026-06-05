"""Framework-wide shared enums, type aliases, and data classes.

该模块具有零框架内部依赖，可以安全地被所有其他模块导入。

Has zero framework-internal dependencies — safe for all other modules to import.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class LifecycleHook(StrEnum):
    """生命周期钩子阶段枚举。

    定义了框架支持的三个生命周期钩子阶段：
    - AFTER_INIT: 初始化完成后
    - BEFORE_STARTUP: 启动前
    - BEFORE_SHUTDOWN: 关闭前

    Lifecycle phases for hook registration.

    Defines three lifecycle hook phases supported by the framework:
    - AFTER_INIT: After initialization is complete
    - BEFORE_STARTUP: Before startup
    - BEFORE_SHUTDOWN: Before shutdown
    """

    AFTER_INIT = "after_init"
    BEFORE_STARTUP = "before_startup"
    BEFORE_SHUTDOWN = "before_shutdown"


HookFunction = Callable[..., object]
"""钩子函数类型别名。

表示可以接受任意参数并返回任意类型的函数。

Type alias for hook functions.

Represents a function that can accept any arguments and return any type.
"""


class LifecycleAware(Protocol):
    """生命周期感知接口。

    定义服务和模块必须实现的生命周期方法。

    Lifecycle-aware interface.

    Defines lifecycle methods that services and modules must implement.
    """

    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...


@dataclass(slots=True)
class ServiceMeta:
    """@service装饰的类存储的元数据。

    Attributes:
        name: 服务的全局唯一名称。

    Metadata stored on a @service-decorated class.

    Attributes:
        name: Globally unique service name.
    """

    name: str


@dataclass(slots=True)
class ModuleMeta(ServiceMeta):
    """@module装饰的类存储的元数据。

    Attributes:
        name: 模块的全局唯一名称。
        services: 直接子服务列表。

    Metadata stored on a @module-decorated class.

    Attributes:
        name: Globally unique module name.
        services: Direct child services list.
    """

    services: list[type] = field(default_factory=list)


@dataclass(slots=True)
class RouterMeta(ServiceMeta):
    """@router装饰的类存储的元数据。

    Attributes:
        name: 路由器的全局唯一名称。
        prefix: URL前缀，应用于该组中的所有路由。
        tags: 该路由组的OpenAPI标签。
        routes: 路由处理函数列表。

    Metadata stored on a @router-decorated class.

    Attributes:
        name: Globally unique router name.
        prefix: URL prefix applied to all routes in this group.
        tags: OpenAPI tags for this route group.
        routes: List of route handler functions.
    """

    prefix: str = ""
    tags: list[str] = field(default_factory=list)
    routes: list[HookFunction] = field(default_factory=list)


@dataclass(slots=True)
class ServiceEntry:
    """单个@service或@module实例的运行时描述符。

    Attributes:
        cls: 服务/模块的类。
        name: 服务/模块的名称。
        instance: 实例对象，初始为None，在配置阶段创建。

    Runtime descriptor for a single @service or @module instance.

    Attributes:
        cls: The service/module class.
        name: The service/module name.
        instance: Instance object, None initially, created during configuration.
    """

    cls: type
    name: str
    instance: object | None = field(default=None)


# Service标记常量
# Service marker constants
CF_SERVICE_MARKER = "__cf_service__"
CF_SERVICE_META = "__cf_service_meta__"

# 名称属性常量
# Name attribute constant
CF_NAME_ATTR = "__cf_name__"

# 路由属性常量
# Route attribute constant
ROUTE_ATTR = "__cf_route__"

# 生命周期钩子标记映射
# Lifecycle hook marker mapping
CF_HOOK_MARKER_MAP: dict[LifecycleHook, str] = {
    LifecycleHook.AFTER_INIT: "__cf_after_init__",
    LifecycleHook.BEFORE_STARTUP: "__cf_before_startup__",
    LifecycleHook.BEFORE_SHUTDOWN: "__cf_before_shutdown__",
}


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


def get_service_meta(cls: type) -> ServiceMeta:
    """获取服务类的元数据。

    Args:
        cls: 服务类。

    Returns:
        ServiceMeta对象，如果不存在则返回默认空元数据。

    Get metadata for a service class.

    Args:
        cls: The service class.

    Returns:
        ServiceMeta object, or default empty metadata if not found.
    """
    raw = getattr(cls, CF_SERVICE_META, None)
    if isinstance(raw, ServiceMeta):
        return raw
    return ServiceMeta(name="")


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


def get_module_meta(cls: type) -> ModuleMeta:
    """获取模块类的元数据。

    Args:
        cls: 模块类。

    Returns:
        ModuleMeta对象，如果不存在则返回默认空元数据。

    Get metadata for a module class.

    Args:
        cls: The module class.

    Returns:
        ModuleMeta object, or default empty metadata if not found.
    """
    raw = getattr(cls, CF_SERVICE_META, None)
    if isinstance(raw, ModuleMeta):
        return raw
    return ModuleMeta(name="")


def is_cf_router(cls: type) -> bool:
    """检查类是否被@router装饰器装饰。

    Args:
        cls: 要检查的类。

    Returns:
        如果类被@router装饰器装饰，则返回True；否则返回False。

    Check if a class is decorated with @router.

    Args:
        cls: The class to check.

    Returns:
        True if the class is decorated with @router, False otherwise.
    """
    return isinstance(getattr(cls, CF_SERVICE_META, None), RouterMeta)


def get_router_meta(cls: type) -> RouterMeta | None:
    """获取路由器类的元数据。

    Args:
        cls: 路由器类。

    Returns:
        RouterMeta对象，如果不存在则返回None。

    Get metadata for a router class.

    Args:
        cls: The router class.

    Returns:
        RouterMeta object, or None if not found.
    """
    raw = getattr(cls, CF_SERVICE_META, None)
    if isinstance(raw, RouterMeta):
        return raw
    return None


def resolve_deps(cls: type) -> dict[str, type]:
    """从类的类型注解中解析依赖映射。

    返回 {属性名: 依赖类型}，只包含被@service/@module/@router装饰的类型。

    Args:
        cls: 要解析依赖的类。

    Returns:
        属性名到依赖类型的映射。

    Resolve dependency mapping from class type annotations.

    Returns {attr_name: dep_type} for types decorated with @service, @module, or @router.

    Args:
        cls: The class to resolve dependencies from.

    Returns:
        Mapping of attribute names to dependency types.
    """
    from typing import get_type_hints

    try:
        hints = get_type_hints(cls)
    except Exception:
        return {}
    return {
        name: tp
        for name, tp in hints.items()
        if isinstance(tp, type) and hasattr(tp, CF_SERVICE_MARKER)
    }


__all__ = [
    "CF_HOOK_MARKER_MAP",
    "CF_NAME_ATTR",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "ROUTE_ATTR",
    "HookFunction",
    "LifecycleAware",
    "LifecycleHook",
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
    "resolve_deps",
]
