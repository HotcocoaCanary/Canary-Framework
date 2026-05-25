"""CF 框架 —— 轻量级 Python 服务框架。

核心导出:
    - 装饰器: config, service, module, on_init, on_start, on_end
    - 引擎:   Canary, Context
"""

__version__ = "0.1.0"

from cf.core import (
    Canary,
    Context,
    config,
    module,
    on_end,
    on_init,
    on_start,
    service,
)

__all__ = [
    "Canary",
    "Context",
    "config",
    "module",
    "on_end",
    "on_init",
    "on_start",
    "service",
    "__version__",
]
