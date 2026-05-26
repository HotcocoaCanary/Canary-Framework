"""Module decorator — marks a class as a composable group of services.

设计思路 (Design rationale):
    为什么需要模块？
    （Why do we need modules?）

    模块解决两个问题：
    1. **组合**：将多个服务组织成树形结构。一个模块就是一个 namespace，
       它的 ``services`` 参数定义了该 namespace 下的成员
       Composition: modules organise services into a tree.  Each module
       is a namespace whose ``services`` list defines its members.
    2. **配置继承**：子服务不声明 ``config`` 时自动继承父模块的配置类，
       避免为每个子服务重复声明相同配置
       Config inheritance: child services inherit their parent module's
       config class when they don't declare their own.

    ``@module`` 内部调用 ``@service``，因此模块也是合法的框架服务
    （``is_cf_service(module_cls)`` 返回 ``True``）。元数据通过
    :class:`ModuleMeta`（继承 :class:`ServiceMeta`）存储在同一
    ``__cf_service_meta__`` 属性上。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common._types import ModuleMeta
from canary_framework.core.decorators.service import (
    _SERVICE_META,
    is_cf_service,
    service,
)

# ---------------------------------------------------------------------------
# 标记属性 (Marker attributes)
# ---------------------------------------------------------------------------

_MODULE_ATTR = "_cf_module__"
"""Set to ``True`` on classes decorated with ``@module``.
用于 ``is_cf_module()`` 快速判断，与 ``__cf_service__`` 正交。"""


# ---------------------------------------------------------------------------
# @module 装饰器
# ---------------------------------------------------------------------------


def module(
    name: str,
    *,
    deps: list[type] | None = None,
    services: list[type] | None = None,
) -> Callable[[type], type]:
    """Declare a class as a Canary Framework module.

    将类声明为框架模块（服务的组合容器）。
    内部调用 ``@service`` 设置基础标记，然后覆盖元数据为 :class:`ModuleMeta`。

    Args:
        name: 全局唯一模块名称。
        deps: 依赖的 ``@service`` / ``@module`` 类列表。
        services: 直接子节点（``@service`` 或 ``@module`` 类）列表。

    Returns:
        一个类装饰器。A class decorator.

    Raises:
        TypeError: 如果 ``services`` 中有未被 ``@service`` 或 ``@module``
                   装饰的类，在装饰时立即抛出。

    Example::

        @module(name="AppModule", services=[DBService, UserService])
        class AppModule:
            pass
    """
    _deps = list(deps or ())
    _services = list(services or ())

    def decorator(cls: type) -> type:
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not "
                    f"decorated with @service or @module."
                )

        service(name=name, deps=_deps)(cls)
        meta = ModuleMeta(name=name, deps=_deps, services=_services)
        setattr(cls, _SERVICE_META, meta)
        setattr(cls, _MODULE_ATTR, True)
        return cls

    return decorator


# ---------------------------------------------------------------------------
# 查询工具 (Introspection helpers)
# ---------------------------------------------------------------------------


def is_cf_module(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@module``.

    判断一个类是否被 ``@module`` 装饰过。
    注意：模块也满足 ``is_cf_service()``，因为内部调用了 ``@service``。"""
    return bool(getattr(cls, _MODULE_ATTR, False))


def get_module_meta(cls: type) -> ModuleMeta:
    """Return the :class:`ModuleMeta` instance attached by ``@module``.

    获取 ``@module`` 装饰器设置的元数据实例。
    如果类未被 ``@module`` 装饰，返回默认的空 :class:`ModuleMeta`。"""
    raw: object = getattr(cls, _SERVICE_META, None)
    if isinstance(raw, ModuleMeta):
        return raw
    return ModuleMeta(name="")
