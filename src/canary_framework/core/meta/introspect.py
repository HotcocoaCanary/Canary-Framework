"""Reading a class's declarations back.

自省：读回一个类声明过的依赖与钩子。两者写在同一批类属性里，因此一次 MRO 遍历同时
收集，结果按类缓存——声明在类创建之后不再变化。

钩子按属性名解析，语义与普通方法一致：子类覆盖同名方法即替换，需要叠加时使用
``super()``；不同名的混入钩子各自成立，基类在前。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple, cast
from weakref import WeakKeyDictionary

from canary_framework.core.meta.dep import Dep
from canary_framework.core.meta.phase import PHASES, Phase

_Bound = Callable[[], object]


class Declaration(NamedTuple):
    """Everything one class declares.

    一个类声明的全部内容。

    :ivar deps: 它依赖的类型。基类在前，按定义顺序，按类型去重。
    :ivar hooks: 阶段名到该阶段钩子属性名的映射。基类在前。
    """

    deps: tuple[type, ...]
    hooks: dict[str, tuple[str, ...]]


# 以弱引用为键，动态创建的类仍可被回收。
_cache: WeakKeyDictionary[type, Declaration] = WeakKeyDictionary()


def declaration_of(cls: type) -> Declaration:
    """Return what *cls* declares, scanning once and caching the result.

    返回 *cls* 的声明内容，首次调用时扫描，之后取缓存。
    """
    found = _cache.get(cls)
    if found is None:
        found = _cache[cls] = _scan(cls)
    return found


def deps_of(cls: type) -> tuple[type, ...]:
    """Return the dependencies *cls* declares.

    返回 *cls* 声明的依赖。两个属性指向同一个类只计一条，因为它们取回同一个实例。
    """
    return declaration_of(cls).deps


def hook_names(cls: type, phase: Phase) -> tuple[str, ...]:
    """Return the attribute names of *cls*'s hooks for *phase*.

    返回 *cls* 在 *phase* 上的钩子属性名。空元组表示该阶段在此单元上无事可做。
    """
    return declaration_of(cls).hooks.get(phase.name, ())


def hooks_of(unit: object, phase: Phase) -> list[_Bound]:
    """Return the bound methods of *unit* belonging to *phase*, base-first.

    返回 *unit* 属于 *phase* 的绑定方法，基类在前。
    """
    return [cast("_Bound", getattr(unit, name)) for name in hook_names(type(unit), phase)]


def _scan(cls: type) -> Declaration:
    """Walk the MRO once, collecting dependencies and marked names together.

    逆序遍历 ``__mro__``（基类到派生类），保证基类在前。先收集带过标记的属性名，再对
    每个名字做一次常规属性解析：只有解析到的那一个函数仍带标记时该钩子才成立。
    """
    deps: dict[type, None] = {}  # 有序集合：保留定义顺序并去重
    marked: dict[str, None] = {}
    for owner in reversed(cls.__mro__):
        if owner is object:
            continue  # object 的成员既不是依赖也不带标记
        for name, value in vars(owner).items():
            if isinstance(value, Dep):
                deps[value.cls] = None
            elif callable(value) and _phases_of(value):
                marked.setdefault(name)

    hooks: dict[str, list[str]] = {}
    for name in marked:
        for phase_name in _phases_of(getattr(cls, name, None)):
            hooks.setdefault(phase_name, []).append(name)
    return Declaration(tuple(deps), {name: tuple(v) for name, v in hooks.items()})


def _phases_of(obj: object) -> tuple[str, ...]:
    """Return the phase names *obj* was marked with, if any.

    返回 *obj* 被标记的阶段名。
    """
    return cast("tuple[str, ...]", getattr(obj, PHASES, ()))
