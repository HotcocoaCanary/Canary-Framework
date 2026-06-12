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
    ServiceMeta,
)
from canary_framework.core import ServiceBase


def service() -> Callable[[type], type[ServiceBase]]:
    """声明一个类为可注入服务。

    添加服务标记和元数据，修改类的基类使其继承自ServiceBase。
    服务名称自动生成为``类名 + Service``。
    依赖通过类的类型注解自动检测。
    路由通过类属性 router: Router 定义。

    Returns:
        装饰后的类。

    Declare a class as an injectable service.

    Adds service marker and metadata, modifies the class to inherit from ServiceBase.
    The service name is auto-generated as ``ClassName + Service``.
    Dependencies are auto-detected from class type annotations.
    Routes are defined via the class attribute ``router: Router``.

    Returns:
        The decorated class.
    """

    def decorator(cls: type) -> type[ServiceBase]:
        if not issubclass(cls, ServiceBase):
            raise TypeError(
                f"@service '{cls.__name__}': must inherit from ServiceBase. "
                f"Did you forget 'class {cls.__name__}(ServiceBase):'?"
            )
        name = cls.__name__
        meta = ServiceMeta(name=name)
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, meta)
        setattr(cls, CF_NAME_ATTR, name)
        return cls

    return decorator


__all__ = ["service"]
