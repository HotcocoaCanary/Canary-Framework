"""Marker decorators — declare a unit and its lifecycle hooks.

标记装饰器：声明最小单元与生命周期钩子。只 ``setattr`` 打标记、不改造类，单元因此仍是
普通类，可以正常继承、混入、嵌套。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import overload

from canary_framework.common.markers import COCOA_ATTR, ON_INIT, ON_START, ON_STOP


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

    把类标记为最小单元；``deps`` 里的依赖会在装配期（``Canary(...)``）注入为 snake_case
    属性。用法::

        @cocoa
        class Config: ...

        @cocoa(deps=[Config])          # 注入为 self.config
        class Database: ...
    """
    # 存成元组：不可变，因此 deps_of 可以直接返回它而无需每次复制。
    _deps = tuple(deps or ())

    def mark(c: type[T]) -> type[T]:
        setattr(c, COCOA_ATTR, _deps)
        return c

    return mark(cls) if cls is not None else mark


def on_init[T: Callable[..., object]](fn: T) -> T:
    """Register *fn* as an ``@on_init`` hook.

    注册初始化钩子，由 ``Canary.init()`` 按拓扑序执行；此时依赖已注入，尚无单元开始运行。
    """
    setattr(fn, ON_INIT, True)
    return fn


def on_start[T: Callable[..., object]](fn: T) -> T:
    """Register *fn* as an ``@on_start`` hook.

    注册启动钩子，由 ``Canary.start()`` 按拓扑序执行；获取资源、起后台任务归这里，
    因为只有在此获取的东西才会被 ``@on_stop`` 回收。
    """
    setattr(fn, ON_START, True)
    return fn


def on_stop[T: Callable[..., object]](fn: T) -> T:
    """Register *fn* as an ``@on_stop`` hook.

    注册停止钩子，由 ``Canary.stop()`` 按逆拓扑序执行。
    """
    setattr(fn, ON_STOP, True)
    return fn
