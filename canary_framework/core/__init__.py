"""CF 核心模块 —— 装饰器、引擎、注册中心和工具函数。

公开 API:
    - 装饰器:   config, service, module, on_init, on_start, on_end
    - 引擎类:   Canary, Context
"""

from canary_framework.core.decorators.config import config
from canary_framework.core.decorators.lifecycle import on_end, on_init, on_start
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service
from canary_framework.core.engine.canary import Canary
from canary_framework.core.engine.context import Context

__all__ = [
    "config",
    "service",
    "module",
    "on_init",
    "on_start",
    "on_end",
    "Canary",
    "Context",
]
