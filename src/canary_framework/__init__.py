"""Canary — a minimal dependency-injection and lifecycle runtime.

``@cocoa`` 标记最小单元，:class:`Canary` 编排一组单元：解析依赖图、按拓扑序排序、注入
依赖，并驱动生命周期::

    @cocoa(deps=[Database])
    class UserService: ...

    canary = Canary(UserService)   # 装配：建图、排序、注入依赖
    await canary.init()            # 全部 @on_init
    await canary.start()           # 全部 @on_start
    canary[Database]               # 共享单例
    canary.order                   # 拓扑启动顺序
    await canary.stop()            # 逆序全部 @on_stop
"""

from __future__ import annotations

__version__ = "0.9.3"

from canary_framework.common.error import (
    CanaryError,
    CircularDependencyError,
    ConstructionError,
    InjectionError,
    LifecycleError,
)
from canary_framework.common.type import LifecycleState
from canary_framework.core.decorator import cocoa, on_init, on_start, on_stop
from canary_framework.runtime import Canary

__all__ = [
    "Canary",
    "CanaryError",
    "CircularDependencyError",
    "ConstructionError",
    "InjectionError",
    "LifecycleError",
    "LifecycleState",
    "cocoa",
    "on_init",
    "on_start",
    "on_stop",
]
