"""@module装饰器实现。

将类标记为模块，设置元数据并修改基类继承链。

@module decorator implementation.

Marks classes as modules, sets metadata, and modifies base class chain.
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ModuleMeta,
    is_cf_service,
)
from canary_framework.core import ModuleBase


def module(
    *,
    services: list[type] | None = None,
) -> Callable[[type], type[ModuleBase]]:
    """声明一个类为模块。

    添加模块标记和元数据，修改类的基类使其继承自ModuleBase。
    模块名称自动生成为``类名 + Module``。
    依赖通过类的类型注解自动检测。

    Args:
        services: 模块直接包含的子服务类列表。

    Raises:
        TypeError: 如果services中的任何服务未被装饰。

    Returns:
        装饰后的类。

    Declare a class as a Canary Framework module.

    Adds module marker and metadata, modifies the class to inherit from ModuleBase.
    The module name is auto-generated as ``ClassName + Module``.
    Dependencies are auto-detected from class type annotations.

    Args:
        services: Direct child services.

    Raises:
        TypeError: If any service in ``services`` is not decorated.

    Returns:
        The decorated class.
    """
    _services = list(services or ())

    def decorator(cls: type) -> type[ModuleBase]:
        if not issubclass(cls, ModuleBase):
            raise TypeError(
                f"@module '{cls.__name__}': must inherit from ModuleBase. "
                f"Did you forget 'class {cls.__name__}(ModuleBase):'?"
            )
        name = cls.__name__
        for svc_cls in _services:
            if not is_cf_service(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' "
                    f"is not decorated with @service or @module."
                )

        meta = ModuleMeta(name=name, services=_services)
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, meta)
        setattr(cls, CF_NAME_ATTR, name)
        return cls

    return decorator


__all__ = ["module"]
