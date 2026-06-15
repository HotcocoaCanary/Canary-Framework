"""Framework-wide shared enums, type aliases, and data classes.

该模块具有零框架内部依赖，可以安全地被所有其他模块导入。

Has zero framework-internal dependencies — safe for all other modules to import.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from types import UnionType
from typing import Any, Protocol, cast, get_args, get_origin

from canary_framework.common.config import CanaryConfig


class LifecycleHook(StrEnum):
    """生命周期钩子阶段枚举。

    定义了框架支持的两个生命周期钩子阶段：
    - BEFORE_STARTUP: 启动前
    - BEFORE_SHUTDOWN: 关闭前

    Lifecycle phases for hook registration.

    Defines two lifecycle hook phases supported by the framework:
    - BEFORE_STARTUP: Before startup
    - BEFORE_SHUTDOWN: Before shutdown
    """

    BEFORE_STARTUP = "before_startup"
    BEFORE_SHUTDOWN = "before_shutdown"


HookFunction = Callable[..., object]
"""钩子函数类型别名。

表示可以接受任意参数并返回任意类型的函数。

Type alias for hook functions.

Represents a function that can accept any arguments and return any type.
"""


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


@dataclass(slots=True)
class ServiceMeta:
    """@service装饰的类存储的元数据。

    Attributes:
        name: 服务的全局唯一名称。
        config_cls: 服务的配置类（如有）。

    Metadata stored on a @service-decorated class.

    Attributes:
        name: Globally unique service name.
        config_cls: Optional config class for the service.
    """

    name: str
    config_cls: type[CanaryConfig] | None = None


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


@dataclass(slots=True)
class RouteInfo:
    """单个 HTTP 路由的完整元数据。

    在 Router 的 @router.get/@router.post 等方法中创建，替代原来的无类型 dict。
    预计算 starlette_path、path_params、query_params 和 param_meta，
    避免运行时和 OpenAPI 生成时的重复解析。

    Complete metadata for a single HTTP route.

    Created by Router's @router.get/@router.post etc. methods, replacing the untyped dict.
    Pre-computes starlette_path, path_params, query_params, and param_meta
    to avoid duplicate parsing at runtime and OpenAPI generation time.
    """

    handler: HookFunction
    method: str
    path: str
    starlette_path: str
    path_params: list[str]
    query_params: list[str]
    param_meta: dict[str, object]
    summary: str | None = None
    description: str | None = None
    response_model: type | None = None
    request_model: type | None = None
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    operation_id: str | None = None
    responses: dict[str, object] = field(default_factory=dict)
    router_prefix: str = ""
    router_tags: list[str] = field(default_factory=list)


# 生命周期钩子标记映射
# Lifecycle hook marker mapping
CF_HOOK_MARKER_MAP: dict[LifecycleHook, str] = {
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


def get_service_meta(cls: type) -> ServiceMeta | None:
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
    meta = getattr(cls, CF_SERVICE_META, None)
    if meta is None:
        return None
    return cast(ServiceMeta, meta)


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
    "CF_HOOK_MARKER_MAP",
    "CF_NAME_ATTR",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "HookFunction",
    "LifecycleAware",
    "LifecycleHook",
    "ModuleMeta",
    "RouteInfo",
    "ServiceEntry",
    "ServiceMeta",
    "get_module_meta",
    "get_service_meta",
    "is_cf_module",
    "is_cf_service",
    "unwrap_optional",
]
