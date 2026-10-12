"""Running a graph on test doubles.

带替身启动一张图。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from canary_framework.core import Canary, scope_of


@asynccontextmanager
async def running[T: Canary](
    root: type[T], doubles: Mapping[type[Canary], Canary] | None = None
) -> AsyncIterator[T]:
    """Start a fresh *root* with *doubles* standing in, and reclaim the graph on exit.

    构造一个新的 *root*，登记替身，启动整张图；退出时回收::

        async with running(TelemetryDaemon, {Clock: ManualClock()}) as daemon:
            ...

    替身经 ``Scope.provide`` 登记，因此被替换的单元不会被构造，替身按自身的类型参与生命
    周期：运行自己的钩子，进入自己声明的依赖。每次调用都是一张新的图。

    :param root: 根单元的类型，无参构造。
    :param doubles: 被替换的类型到替身。替身必须是该类型的实例。
    :raises TypeError: 某个替身不是它所替换类型的实例。
    """
    unit = root()
    scope = scope_of(unit)
    for cls, double in (doubles or {}).items():
        scope.provide(cls, double)
    async with unit:
        yield unit
