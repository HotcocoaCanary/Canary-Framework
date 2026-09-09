"""Introspection — read back the markers the decorators wrote.

自省：读取装饰器写下的标记。运行时据此建图并驱动钩子。

这里只有一个算法：一次 MRO 扫描，把三种生命周期标记一起分好桶。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from weakref import WeakKeyDictionary

from canary_framework.common.markers import COCOA_ATTR, ON_INIT, ON_START, ON_STOP

# 需要扫描的标记全集。一遍 MRO 扫完分桶，比每种标记各扫一遍便宜。
_MARKERS = (ON_INIT, ON_START, ON_STOP)

# 每个类的扫描结果：marker -> [(定义它的类, 未绑定函数), ...]
#
# 缓存的理由：MRO 扫描的结果在类创建之后就不再变（装饰器在类定义时就把标记打完了），
# 而同一个类会被反复扫描——一次完整生命周期就要扫三遍。用弱引用作键，动态创建的类
# （测试里到处都是）该回收还是能回收。
_scan_cache: WeakKeyDictionary[type, dict[str, list[tuple[type, Callable[..., object]]]]]
_scan_cache = WeakKeyDictionary()


def is_cocoa(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@cocoa``.

    判断类是否被 ``@cocoa`` 标记过。注意不能用 ``deps_of(cls)`` 的真假来代替——
    没有依赖的单元返回空元组，那也是一个合法的单元。
    """
    return hasattr(cls, COCOA_ATTR)


def deps_of(cls: type) -> tuple[type, ...]:
    """Return the dependencies declared by ``@cocoa(deps=[...])``.

    返回 ``@cocoa(deps=[...])`` 声明的依赖。存的就是一个元组，这里直接返回它、不复制
    ——元组不可变，共享是安全的，而这个函数在建图、拓扑排序、注入、摘要里都要被调用，
    每次都拷一份纯属浪费。
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

    扫描实例所属类的整条 MRO，返回带该标记的方法，**基类在前**。两条规则值得写下来：

    - **基类优先。** 混入（mixin）的钩子先于本类执行，让两者"叠加"而不是互相覆盖
      （借鉴 FastStream 的 ``on_startup`` 栈式钩子）。
    - **按函数身份去重。** 子类继承而不覆盖时，同一个函数对象会在 MRO 里出现多次，
      只能算一次；反过来，子类若真的覆盖了它，那就是另一个函数对象，理应生效。
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

    整条 MRO 只走一遍，把三种标记一次分好桶——各扫一遍类字典不如一遍扫完分三个桶。
    ``__mro__`` 逆序遍历（object → 派生类）保证基类优先。
    """
    found: dict[str, list[tuple[type, Callable[..., object]]]] = {}
    seen: dict[str, set[Callable[..., object]]] = {}
    for owner in reversed(cls.__mro__):
        if owner is object:
            # object 有二十多个可调用成员，一个都不可能带我们的标记。不跳过的话，光它
            # 一个类就要做上百次 getattr——而每个类的 MRO 末端都是它。
            continue
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
