"""CF 核心模块 —— 装饰器、引擎、注册中心和工具函数。

公开 API:
    - 装饰器:   config, service, module, on_init, on_start, on_end
    - 引擎类:   Canary, Context
"""
from cf.core.decorators.config import config
from cf.core.decorators.service import service
from cf.core.decorators.module import module
from cf.core.decorators.lifecycle import on_init, on_start, on_end
from cf.core.engine.canary import Canary
from cf.core.engine.context import Context

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
