"""Metadata attribute names and accessor functions.

这些标记由装饰器设置在类上，并由引擎读取。
将它们放在common模块中是避免循环导入的关键。

These markers are set on classes by decorators and read by the engine.
Placing them in common is the key to avoiding circular imports.
"""

from __future__ import annotations

from .types import LifecycleHook, ModuleMeta, RouterMeta, ServiceMeta

# Service标记常量
# Service marker constants
CF_SERVICE_MARKER = "__cf_service__"
CF_SERVICE_META = "__cf_service_meta__"

# Module标记常量
# Module marker constants
CF_MODULE_MARKER = "__cf_module__"

# Router标记常量
# Router marker constants
CF_ROUTER_MARKER = "__cf_router__"

# 名称属性常量
# Name attribute constant
CF_NAME_ATTR = "__cf_name__"

# 路由属性常量
# Route attribute constant
ROUTE_ATTR = "__cf_route__"

# 生命周期钩子标记映射
# Lifecycle hook marker mapping
CF_HOOK_MARKER_MAP: dict[LifecycleHook, str] = {
    LifecycleHook.AFTER_CONFIG: "__cf_after_config__",
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
    return bool(getattr(cls, CF_MODULE_MARKER, False))


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
    return bool(getattr(cls, CF_ROUTER_MARKER, False))


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


__all__ = [
    "CF_HOOK_MARKER_MAP",
    "CF_MODULE_MARKER",
    "CF_NAME_ATTR",
    "CF_ROUTER_MARKER",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "ROUTE_ATTR",
    "get_module_meta",
    "get_service_meta",
    "is_cf_module",
    "is_cf_router",
    "is_cf_service",
]
