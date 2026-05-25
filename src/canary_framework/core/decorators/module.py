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

    模块本身也是服务（``is_cf_service(module_cls)`` 在 verify 阶段通过），
    因此模块可以嵌套，也支持生命周期钩子。

    装饰顺序 (Decorator stacking order):
        ``@web()`` 必须放在 ``@module`` 下面（更接近类定义），因为 Python
        装饰器从下往上执行：最底层的装饰器最先包装类。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common._types import ModuleMeta
from canary_framework.core.decorators.service import is_cf_service

# ---------------------------------------------------------------------------
# 标记属性 (Marker attributes)
# ---------------------------------------------------------------------------

_MODULE_ATTR = "_cf_module__"
"""Set to ``True`` on classes decorated with ``@module``."""

_MODULE_META = "_cf_module_meta__"
"""Stores a :class:`ModuleMeta` dict on decorated classes."""


# ---------------------------------------------------------------------------
# @module 装饰器
# ---------------------------------------------------------------------------


def module(
    name: str,
    *,
    config: type | None = None,
    services: list[type] | None = None,
) -> Callable[[type], type]:
    """Declare a class as a Canary Framework module.

    将类声明为框架模块（服务的组合容器）。

    Args:
        name: 全局唯一模块名称。
              Globally unique module name.
        config: 可选的 ``@config`` 装饰的配置类。子服务未声明 ``config``
                时自动继承此配置。
                Optional ``@config``-decorated class shared by child services.
        services: 直接子节点（``@service`` 或 ``@module`` 类）列表。
                  List of child ``@service`` / ``@module`` classes.

    Returns:
        一个类装饰器。A class decorator.

    Raises:
        TypeError: 如果 ``services`` 中有未被 ``@service`` 或 ``@module``
                   装饰的类，在装饰时立即抛出。

    Example::

        @module(name="AppModule", config=AppConfig, services=[DBService, UserService])
        class AppModule:
            pass
    """
    _config = config
    _services = list(services or ())

    def decorator(cls: type) -> type:
        # 装饰时校验：确保所有子节点都是合法的框架类
        # Validate at decoration time: all children must be framework classes
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not "
                    f"decorated with @service or @module."
                )

        meta: ModuleMeta = {
            "name": name,
            "config_cls": _config,
            "services": _services,
        }
        setattr(cls, _MODULE_ATTR, True)
        setattr(cls, _MODULE_META, meta)
        cls.__cf_name__ = name  # type: ignore[attr-defined]
        return cls

    return decorator


# ---------------------------------------------------------------------------
# 查询工具 (Introspection helpers)
# ---------------------------------------------------------------------------


def is_cf_module(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@module``.

    判断一个类是否被 ``@module`` 装饰过。"""
    return bool(getattr(cls, _MODULE_ATTR, False))


def get_module_meta(cls: type) -> ModuleMeta:
    """Return the :class:`ModuleMeta` dictionary attached by ``@module``.

    获取 ``@module`` 装饰器设置的元数据字典。
    如果类未被装饰，返回空的 :class:`ModuleMeta`。"""
    raw: object = getattr(cls, _MODULE_META, {})
    if isinstance(raw, dict):
        return raw  # type: ignore[return-value]
    return {}
