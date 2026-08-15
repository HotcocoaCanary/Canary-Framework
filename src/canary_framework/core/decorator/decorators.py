"""Marker decorators — declare a unit and its lifecycle hooks.

标记装饰器：声明最小单元与生命周期钩子。只 ``setattr`` 打标记、不改造类，
因此单元仍是普通类，可以廉价地继承 / 混入 / 嵌套。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import overload

from canary_framework.core.infra.markers import _COCOA_ATTR, _ON_INIT, _ON_START, _ON_STOP


@overload
def cocoa[T](cls: type[T]) -> type[T]: ...


@overload
def cocoa[T](
    cls: None = None,
    *,
    deps: list[type] | None = None,
) -> Callable[[type[T]], type[T]]: ...


def cocoa[T](
    cls: type[T] | None = None,
    *,
    deps: list[type] | None = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """Mark a class as a cocoa (the minimum unit), optionally with dependencies.

    把类标记为最小单元；``deps`` 里的依赖会在 ``start`` 阶段注入为 snake_case 属性。用法::

        @cocoa
        class Config: ...

        @cocoa(deps=[Config])          # 注入为 self.config
        class Database: ...
    """
    _deps = list(deps or ())

    def mark(c: type[T]) -> type[T]:
        setattr(c, _COCOA_ATTR, _deps)
        return c

    return mark(cls) if cls is not None else mark


def on_init[T: Callable[..., object]](fn: T) -> T:
    """Register *fn* as an ``init`` hook (runs in topological order).

    注册初始化钩子，按拓扑序执行。
    """
    setattr(fn, _ON_INIT, True)
    return fn


def on_start[T: Callable[..., object]](fn: T) -> T:
    """Register *fn* as a ``start`` hook (topological order, deps already injected).

    注册启动钩子，按拓扑序执行；此时依赖已注入完成。
    """
    setattr(fn, _ON_START, True)
    return fn


def on_stop[T: Callable[..., object]](fn: T) -> T:
    """Register *fn* as a ``stop`` hook (runs in reverse topological order).

    注册停止钩子，按逆拓扑序执行。
    """
    setattr(fn, _ON_STOP, True)
    return fn
