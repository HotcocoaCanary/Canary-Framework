"""Reaching a unit in a graph by its type.

按类型取回图上的单元。
"""

from __future__ import annotations

from typing import cast

from canary_framework.core import Canary, scope_of


def unit[T: Canary](root: Canary, cls: type[T]) -> T:
    """Return the instance of *cls* in the graph *root* belongs to.

    返回 *root* 所在的图上 *cls* 的实例。日常代码应当从声明依赖的单元上读
    （``daemon.collector.store``）；测试常常要够到一个自己没有声明过依赖的单元，这时用它::

        async with running(TelemetryDaemon) as daemon:
            store = unit(daemon, MetricStore)

    经 ``provide`` 登记过替身时，取回的是替身。

    :param root: 图上的任意一个单元，通常是根。
    :param cls: 要取回的单元类型。
    :raises LookupError: 图上没有 *cls*。图在第一次进入生命周期时才建立，在那之前只有
        *root* 自己和已登记的替身。
    """
    instances = scope_of(root).instances
    if cls not in instances:
        raise LookupError(
            f"unit({type(root).__name__}(), {cls.__name__}): no {cls.__name__} in this graph. "
            f"The graph is built when the lifecycle begins."
        )
    return cast("T", instances[cls])
