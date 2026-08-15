"""The stable core — declaration primitives (decorators, naming, markers).

稳定核心：声明层原语（装饰器 / 命名 / 标记）。运行时引擎已抽到
:mod:`canary_framework.runtime`；服务入口由各单元在 ``start()`` 阶段暴露，运行时按
鸭子类型委托给它们。
"""

from canary_framework.core.decorator import (
    cocoa,
    deps_of,
    init_hooks,
    is_cocoa,
    on_init,
    on_start,
    on_stop,
    start_hooks,
    stop_hooks,
)
from canary_framework.core.infra import to_snake

__all__ = [
    "cocoa",
    "deps_of",
    "init_hooks",
    "is_cocoa",
    "on_init",
    "on_start",
    "on_stop",
    "start_hooks",
    "stop_hooks",
    "to_snake",
]
