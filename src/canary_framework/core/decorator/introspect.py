"""Introspection — read back the markers the decorators wrote.

自省：读取装饰器写下的标记，供运行时建图与驱动钩子。核心是一次 MRO 扫描，一遍把三种
生命周期标记分好桶。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from weakref import WeakKeyDictionary

from canary_framework.common.markers import COCOA_ATTR, ON_INIT, ON_START, ON_STOP

# 需要扫描的标记全集。一遍 MRO 扫完分桶，比每种标记各扫一遍便宜。
_MARKERS = (ON_INIT, ON_START, ON_STOP)

# 每个类的扫描结果：marker -> [(定义它的类, 未绑定函数), ...]。
# 标记在类定义时就写好、之后不再变，所以扫描结果可以缓存；用弱引用作键，动态创建的类
# 仍可被回收。
_scan_cache: WeakKeyDictionary[type, dict[str, list[tuple[type, Callable[..., object]]]]]
_scan_cache = WeakKeyDictionary()


def is_cocoa(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@cocoa``.

    判断类是否被 ``@cocoa`` 标记过。不能用 ``deps_of(cls)`` 的真假代替：没有依赖的单元
    返回空元组，它同样是合法单元。
    """
    return hasattr(cls, COCOA_ATTR)


def deps_of(cls: type) -> tuple[type, ...]:
    """Return the dependencies declared by ``@cocoa(deps=[...])``.

    返回 ``@cocoa(deps=[...])`` 声明的依赖。返回的是存储中那个元组本身（不可变，共享安全）。
    """
    return cast("tuple[type, ...]", getattr(cls, COCOA_ATTR, ()))


def init_hooks(instance: object) -> list[Callable[[], object]]:
    """The ``@on_init`` hooks of *instance*, base-first.

    该实例的 ``@on_init`` 钩子，基类在前。
    """
    return _hooks(instance, ON_INIT)


def start_hooks(instance: object) -> list[Callable[[], object]]:
    """The ``@on_start`` hooks of *instance*, base-first.

    该实例的 ``@on_start`` 钩子，基类在前。
    """
    return _hooks(instance, ON_START)


def stop_hooks(instance: object) -> list[Callable[[], object]]:
    """The ``@on_stop`` hooks of *instance*, base-first (the runtime runs them in reverse).

    该实例的 ``@on_stop`` 钩子，基类在前——逆序是**单元之间**的事，由运行时按拓扑逆序
    调度；同一个单元内部的多个停止钩子仍按定义序执行。
    """
    return _hooks(instance, ON_STOP)


def _hooks(instance: object, marker: str) -> list[Callable[[], object]]:
    """Bind every method of *instance* carrying *marker*, base-first.

    扫描实例所属类的整条 MRO，返回带该标记的绑定方法。两条规则：

    - **基类在前。** 混入（mixin）的钩子先于本类的钩子执行，两者叠加而非互相覆盖。
    - **按函数身份去重。** 子类继承而不覆盖时同一函数对象会在 MRO 中出现多次，只算一次；
      子类若覆盖了它，那是另一个函数对象，照常生效。
    """
    cls = type(instance)
    by_marker = _scan_cache.get(cls)
    if by_marker is None:
        by_marker = _scan_cache[cls] = _scan(cls)
    return [
        cast("Callable[[], object]", raw.__get__(instance, owner))
        for owner, raw in by_marker.get(marker, ())
    ]


def _scan(cls: type) -> dict[str, list[tuple[type, Callable[..., object]]]]:
    """Walk the MRO once and bucket every marked method by its marker.

    整条 MRO 只走一遍，三种标记一次分桶。``__mro__`` 逆序遍历（object → 派生类）保证
    基类在前。
    """
    found: dict[str, list[tuple[type, Callable[..., object]]]] = {}
    seen: dict[str, set[Callable[..., object]]] = {}
    for owner in reversed(cls.__mro__):
        if owner is object:
            continue  # object 的成员不可能带标记，跳过可省下每个类上百次 getattr
        for raw in owner.__dict__.values():
            if not callable(raw):
                continue
            for marker in _MARKERS:
                if getattr(raw, marker, None) is None:
                    continue
                if raw in seen.setdefault(marker, set()):
                    continue
                seen[marker].add(raw)
                found.setdefault(marker, []).append((owner, raw))
    return found
