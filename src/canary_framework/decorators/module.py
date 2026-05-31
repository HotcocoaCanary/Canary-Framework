"""@module装饰器实现。

将类标记为模块，设置元数据并修改基类继承链。

@module decorator implementation.

Marks classes as modules, sets metadata, and modifies base class chain.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common import (
    CF_MODULE_MARKER,
    ModuleMeta,
    is_cf_service,
)
from canary_framework.core import ModuleBase
from canary_framework.engine import make_subclass


def module(
    name: str,
    *,
    deps: list[type] | None = None,
    services: list[type] | None = None,
    config: type | None = None,
) -> Callable[[type], type[ModuleBase]]:
    """声明一个类为模块。

    添加模块标记和元数据，修改类的基类使其继承自ModuleBase。

    Args:
        name: 模块的全局唯一名称。
        deps: 模块依赖的其他模块/服务类列表。
        services: 模块直接包含的子服务类列表。
        config: 可选的模块配置类。

    Raises:
        TypeError: 如果services中的任何服务未被装饰。

    Returns:
        装饰后的类。

    Declare a class as a Canary Framework module.

    Adds module marker and metadata, modifies the class to inherit from ModuleBase.

    Args:
        name: Globally unique module name.
        deps: Dependency classes.
        services: Direct child nodes.
        config: Optional per-module config class.

    Raises:
        TypeError: If any service in ``services`` is not decorated.

    Returns:
        The decorated class.
    """
    _deps = list(deps or ())
    _services = list(services or ())

    def decorator(cls: type) -> type[ModuleBase]:
        for svc_cls in _services:
            if not is_cf_service(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' "
                    f"is not decorated with @service or @module."
                )

        meta = ModuleMeta(
            name=name,
            deps=_deps,
            services=_services,
            config_cls=config,
        )

        return cast(
            "type[ModuleBase]",
            make_subclass(cls, ModuleBase, meta, name, extra_marker=CF_MODULE_MARKER),
        )

    return decorator


__all__ = ["module"]
