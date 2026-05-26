"""Service decorator — marks a class as a Canary Framework service.

设计思路 (Design rationale):
    为什么叫 "service" 而不是 "component" / "bean" / "provider"？
    （Why "service" and not "component", "bean", or "provider"?）

    框架的核心哲学是「服务即最小单元」。这个命名直接告诉用户：
    每一个被装饰的类就是一个独立的服务，它拥有自己的配置、依赖和生命周期。
    The name "service" directly conveys the framework philosophy:
    every decorated class is a self-contained service with its own
    config, dependencies, and lifecycle.

    为什么使用 setattr 存储元数据而不是全局注册表？
    （Why ``setattr`` on the class instead of a global registry?）

    装饰器在类定义时立即执行，此时全局 Registry 尚未创建（Registry 在
    ``Canary.init()`` 中才实例化）。将元数据附着在类上是一种延迟绑定
    策略——类携带自己的「身份证」，Registry 在收集阶段自行提取。
    The decorator fires at class definition time, before the Registry
    exists.  Storing metadata on the class is a deferred-binding strategy:
    the class carries its own "identity card", consumed by Registry later.
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common._types import ServiceMeta

# ---------------------------------------------------------------------------
# 标记属性 (Marker attributes)
# ---------------------------------------------------------------------------

_SERVICE_ATTR = "__cf_service__"
"""Set to ``True`` on classes decorated with ``@service``.
用于 ``is_cf_service()`` 快速判断一个类是否为框架服务。"""

_SERVICE_META = "__cf_service_meta__"
"""Stores a :class:`ServiceMeta` instance on decorated classes.
存储服务的完整元数据，由 Registry 在注册阶段读取。
``@module`` 和 ``@router`` 会覆盖为 ``ModuleMeta`` / ``RouterMeta``。"""


# ---------------------------------------------------------------------------
# @service 装饰器
# ---------------------------------------------------------------------------


def service(
    name: str,
    *,
    deps: list[type] | None = None,
) -> Callable[[type], type]:
    """Declare a class as a Canary Framework service.

    将类声明为框架服务（最小运行单元）。

    Args:
        name: 全局唯一名称，用于依赖声明和注册表查找。
        deps: 依赖的 ``@service`` / ``@module`` 类列表。
              框架将其实例按 snake_case 注入为属性。

    Returns:
        一个类装饰器。A class decorator.

    Example::

        @service(name="database", deps=[CacheService])
        class DBService:
            cache_service: CacheService
    """
    _deps = list(deps or ())

    def decorator(cls: type) -> type:
        meta = ServiceMeta(name=name, deps=_deps)
        setattr(cls, _SERVICE_ATTR, True)
        setattr(cls, _SERVICE_META, meta)
        cls.__cf_name__ = name  # type: ignore[attr-defined]
        return cls

    return decorator


# ---------------------------------------------------------------------------
# 查询工具 (Introspection helpers)
# ---------------------------------------------------------------------------


def is_cf_service(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@service``.

    判断一个类是否被 ``@service`` 装饰过。用于区分普通类和框架服务。

    ``@module`` 和 ``@router`` 由于内部调用了 ``service()``，
    因此 ``is_cf_service()`` 也对它们返回 ``True``。"""
    return bool(getattr(cls, _SERVICE_ATTR, False))


def get_service_meta(cls: type) -> ServiceMeta:
    """Return the :class:`ServiceMeta` instance attached by the decorator.

    获取装饰器设置的元数据实例。
    如果类被 ``@module`` 或 ``@router`` 装饰，返回的可能是
    :class:`ModuleMeta` 或 :class:`RouterMeta`（均为 ``ServiceMeta`` 子类）。

    Returns a default :class:`ServiceMeta` if the class was never decorated.
    """
    raw: object = getattr(cls, _SERVICE_META, None)
    if isinstance(raw, ServiceMeta):
        return raw
    return ServiceMeta(name="")
