"""@service装饰器实现。

将类标记为可注入服务，设置元数据并修改基类继承链。

@service decorator implementation.

Marks classes as injectable services, sets metadata, and modifies base class chain.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ServiceMeta,
)
from canary_framework.core import ServiceBase


def _make_subclass(
    cls: type,
    base: type,
    meta: ServiceMeta,
    name: str,
    *,
    extra_marker: str | None = None,
) -> type:
    """创建子类，用于继承基类。

    Creates a subclass for inheriting from a base class.
    """
    new_cls = type(cls.__name__, (base, cls), {})
    new_cls.__module__ = cls.__module__
    new_cls.__qualname__ = cls.__qualname__
    setattr(new_cls, CF_SERVICE_MARKER, True)
    setattr(new_cls, CF_SERVICE_META, meta)
    setattr(new_cls, CF_NAME_ATTR, name)
    if extra_marker is not None:
        setattr(new_cls, extra_marker, True)
    return new_cls


def service(
    name: str,
    *,
    deps: list[type] | None = None,
) -> Callable[[type], type[ServiceBase]]:
    """声明一个类为可注入服务。

    添加服务标记和元数据，修改类的基类使其继承自ServiceBase。

    Args:
        name: 服务的全局唯一名称。
        deps: 服务依赖的其他服务类列表。

    Returns:
        装饰后的类。

    Declare a class as an injectable service.

    Adds service marker and metadata, modifies the class to inherit from ServiceBase.

    Args:
        name: Globally unique service name.
        deps: Dependency classes injected as snake_case attributes.

    Returns:
        The decorated class.
    """
    _deps = list(deps or ())

    def decorator(cls: type) -> type[ServiceBase]:
        meta = ServiceMeta(name=name, deps=_deps)
        return cast("type[ServiceBase]", _make_subclass(cls, ServiceBase, meta, name))

    return decorator


__all__ = ["service"]