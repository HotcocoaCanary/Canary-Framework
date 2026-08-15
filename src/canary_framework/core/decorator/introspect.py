"""Introspection — read back the markers the decorators wrote.

自省：读取装饰器写下的标记。运行时据此建图并驱动钩子。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from canary_framework.common.markers import COCOA_ATTR, ON_INIT, ON_START, ON_STOP


def is_cocoa(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@cocoa``.

    判断类是否被 ``@cocoa`` 标记过。
    """
    return hasattr(cls, COCOA_ATTR)


def deps_of(cls: type) -> list[type]:
    """Return the dependencies declared by ``@cocoa(deps=[...])``.

    返回 ``@cocoa(deps=[...])`` 声明的依赖列表。
    """
    return cast(list[type], list(getattr(cls, COCOA_ATTR, ())))


def hooks_of(instance: object, marker: str) -> list[Callable[[], object]]:
    """Return the marked methods of *instance*, base-first (mixins before class).

    一个标记可被多个方法共享——它们都会执行，混入的钩子先于本类、其余按定义序。
    这让混入钩子与类自身钩子“叠加”而非互相覆盖（借鉴 FastStream 的 ``on_startup`` 栈式钩子）。
    """
    cls = type(instance)
    hooks: list[Callable[[], object]] = []
    seen: set[str] = set()
    for klass in reversed(cls.__mro__):  # 基类 → 派生类，保证混入的钩子先执行
        for name in klass.__dict__:
            if name in seen:
                continue
            seen.add(name)
            fn = getattr(instance, name, None)
            if callable(fn) and getattr(fn, marker, False):
                hooks.append(fn)
    return hooks


def init_hooks(instance: object) -> list[Callable[[], object]]:
    return hooks_of(instance, ON_INIT)


def start_hooks(instance: object) -> list[Callable[[], object]]:
    return hooks_of(instance, ON_START)


def stop_hooks(instance: object) -> list[Callable[[], object]]:
    return hooks_of(instance, ON_STOP)
