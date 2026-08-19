"""Canary — a minimal dependency-injection and lifecycle framework.

``@cocoa`` marks a class as the minimum unit; a :class:`Canary` orchestrates a
group of them.  It resolves the dependency graph (units nest via ``deps=[...]``),
topologically sorts it to get the startup order, and drives the lifecycle::

    @cocoa(deps=[Database])
    class UserService: ...

    app = Canary(UserService)                 # compose / nest
    await app.init()                          # build the graph
    await app.start()                         # inject deps + run @on_start
    app[Database]                             # shared singleton
    app.order                                 # topological startup order
    await app.stop()

中文版：``@cocoa`` 标记最小单元，:class:`Canary` 编排一组单元——解析依赖图、
按拓扑序得到启动顺序，并驱动生命周期。
"""

from __future__ import annotations

__version__ = "0.9.2"

from canary_framework.common.error import CanaryError, CircularDependencyError, LifecycleError
from canary_framework.common.type import LifecycleState
from canary_framework.core.decorator import cocoa, on_init, on_start, on_stop
from canary_framework.runtime import Canary

__all__ = [
    "Canary",
    "CanaryError",
    "CircularDependencyError",
    "LifecycleError",
    "LifecycleState",
    "cocoa",
    "on_init",
    "on_start",
    "on_stop",
]
