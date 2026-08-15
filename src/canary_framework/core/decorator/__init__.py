"""Marker decorators — the declaration layer (``@cocoa`` + lifecycle hooks).

声明层：``@cocoa`` / ``@on_init`` / ``@on_start`` / ``@on_stop`` 及其自省工具。
只打标记、不改造类；运行时读取标记来建图与驱动生命周期。
"""

from canary_framework.core.decorator.decorators import cocoa, on_init, on_start, on_stop
from canary_framework.core.decorator.introspect import (
    deps_of,
    init_hooks,
    is_cocoa,
    start_hooks,
    stop_hooks,
)

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
]
