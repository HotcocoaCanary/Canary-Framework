"""@service装饰器实现。

将类标记为可注入服务，设置元数据并修改基类继承链。

@service decorator implementation.

Marks classes as injectable services, sets metadata, and modifies base class chain.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import ServiceMeta
from canary_framework.core import ServiceBase
from canary_framework.engine import make_subclass


def service(
    *,
    deps: list[type] | None = None,
) -> Callable[[type], type[ServiceBase]]:
    """声明一个类为可注入服务。

    添加服务标记和元数据，修改类的基类使其继承自ServiceBase。
    服务名称自动生成为``类名 + Service``。

    Args:
        deps: 服务依赖的其他服务类列表。

    Returns:
        装饰后的类。

    Declare a class as an injectable service.

    Adds service marker and metadata, modifies the class to inherit from ServiceBase.
    The service name is auto-generated as ``ClassName + Service``.

    Args:
        deps: Dependency classes injected as snake_case attributes.

    Returns:
        The decorated class.
    """
    _deps = list(deps or ())

    def decorator(cls: type) -> type[ServiceBase]:
        name = cls.__name__ + "Service"
        meta = ServiceMeta(name=name, deps=_deps)
        return cast("type[ServiceBase]", make_subclass(cls, ServiceBase, meta, name))

    return decorator


__all__ = ["service"]
