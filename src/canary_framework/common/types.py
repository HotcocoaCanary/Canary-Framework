"""Framework-wide shared enums, type aliases, and data classes.

该模块具有零框架内部依赖，可以安全地被所有其他模块导入。

Has zero framework-internal dependencies — safe for all other modules to import.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class LifecycleHook(StrEnum):
    """生命周期钩子阶段枚举。

    定义了框架支持的四个生命周期钩子阶段：
    - AFTER_CONFIG: 配置完成后
    - AFTER_INIT: 初始化完成后
    - BEFORE_STARTUP: 启动前
    - BEFORE_SHUTDOWN: 关闭前

    Lifecycle phases for hook registration.

    Defines four lifecycle hook phases supported by the framework:
    - AFTER_CONFIG: After configuration is complete
    - AFTER_INIT: After initialization is complete
    - BEFORE_STARTUP: Before startup
    - BEFORE_SHUTDOWN: Before shutdown
    """

    AFTER_CONFIG = "after_config"
    AFTER_INIT = "after_init"
    BEFORE_STARTUP = "before_startup"
    BEFORE_SHUTDOWN = "before_shutdown"


HookFunction = Callable[..., object]
"""钩子函数类型别名。

表示可以接受任意参数并返回任意类型的函数。

Type alias for hook functions.

Represents a function that can accept any arguments and return any type.
"""


@dataclass(slots=True)
class ServiceMeta:
    """@service装饰的类存储的元数据。

    Attributes:
        name: 服务的全局唯一名称。
        deps: 依赖的服务类列表。

    Metadata stored on a @service-decorated class.

    Attributes:
        name: Globally unique service name.
        deps: List of dependency classes.
    """

    name: str
    deps: list[type] = field(default_factory=list)


@dataclass(slots=True)
class ModuleMeta(ServiceMeta):
    """@module装饰的类存储的元数据。

    继承自ServiceMeta，添加了模块特有的属性。

    Attributes:
        name: 模块的全局唯一名称。
        deps: 依赖的模块/服务类列表。
        services: 直接子服务列表。

    Metadata stored on a @module-decorated class.

    Inherits from ServiceMeta with module-specific attributes.

    Attributes:
        name: Globally unique module name.
        deps: List of dependency classes.
        services: Direct child services list.
    """

    services: list[type] = field(default_factory=list)


@dataclass(slots=True)
class RouterMeta(ServiceMeta):
    """@router装饰的类存储的元数据。

    继承自ServiceMeta，添加了路由器特有的属性。

    Attributes:
        name: 路由器的全局唯一名称。
        deps: 依赖的服务类列表。
        prefix: URL前缀，应用于该组中的所有路由。
        tags: 该路由组的OpenAPI标签。
        routes: 路由处理函数列表。

    Metadata stored on a @router-decorated class.

    Inherits from ServiceMeta with router-specific attributes.

    Attributes:
        name: Globally unique router name.
        deps: List of dependency classes.
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

    在服务注册和依赖注入过程中使用。

    Attributes:
        cls: 服务/模块的类。
        name: 服务/模块的名称。
        instance: 实例对象，初始为None，在配置阶段创建。
        deps: 依赖的类列表。
        dep_names: 依赖的名称列表。

    Runtime descriptor for a single @service or @module instance.

    Used during service registration and dependency injection.

    Attributes:
        cls: The service/module class.
        name: The service/module name.
        instance: Instance object, None initially, created during configuration.
        deps: List of dependency classes.
        dep_names: List of dependency names.
    """

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
