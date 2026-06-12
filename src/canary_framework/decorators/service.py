"""@service装饰器实现。

将类标记为可注入服务，设置元数据并修改基类继承链。

@service decorator implementation.

Marks classes as injectable services, sets metadata, and modifies base class chain.
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ROUTE_ATTR,
    HookFunction,
    ServiceMeta,
)
from canary_framework.core import ServiceBase


def service(
    *,
    prefix: str = "",
    tags: list[str] | None = None,
) -> Callable[[type], type[ServiceBase]]:
    """声明一个类为可注入服务，可选地提供路由能力。

    添加服务标记和元数据，修改类的基类使其继承自ServiceBase。
    服务名称自动生成为``类名 + Service``。
    依赖通过类的类型注解自动检测（例如 ``db: DatabaseService``）。

    当提供 prefix 或 tags 时，服务获得路由挂载能力，等同于原 @router 装饰器。

    Args:
        prefix: 应用于此服务中所有路由的URL前缀。
        tags: 此服务的OpenAPI标签。

    Returns:
        装饰后的类。

    Declare a class as an injectable service, optionally with routing capability.

    Adds service marker and metadata, modifies the class to inherit from ServiceBase.
    The service name is auto-generated as ``ClassName + Service``.
    Dependencies are auto-detected from class type annotations (e.g., ``db: DatabaseService``).

    When prefix or tags are provided, the service gains route mounting capability,
    equivalent to the original @router decorator.

    Args:
        prefix: URL prefix applied to all routes in this service.
        tags: OpenAPI tags for this service.

    Returns:
        The decorated class.
    """
    _tags = list(tags or [])

    def decorator(cls: type) -> type[ServiceBase]:
        if not issubclass(cls, ServiceBase):
            raise TypeError(
                f"@service '{cls.__name__}': must inherit from ServiceBase. "
                f"Did you forget 'class {cls.__name__}(ServiceBase):'?"
            )
        name = cls.__name__ + "Service"
        routes: list[HookFunction] = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if callable(attr) and hasattr(attr, ROUTE_ATTR):
                routes.append(attr)

        meta = ServiceMeta(
            name=name,
            prefix=prefix,
            tags=_tags,
            routes=routes,
        )
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, meta)
        setattr(cls, CF_NAME_ATTR, name)
        return cls

    return decorator


__all__ = ["service"]
