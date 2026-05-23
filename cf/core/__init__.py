# 从各子模块导入框架核心的公开 API，统一对外暴露
from cf.core.decorators.config import config          # @config 装饰器：将类转为 pydantic-settings 配置类
from cf.core.decorators.service import service        # @service 装饰器：声明服务（框架最小运行单元）
from cf.core.decorators.module import module          # @module 装饰器：声明模块（服务的组合容器）
from cf.core.decorators.lifecycle import on_init, on_start, on_end  # 生命周期钩子装饰器
from cf.core.engine.canary import Canary              # Canary 引擎：框架的启动编排器
from cf.core.engine.context import Context            # 上下文对象：在 on_init 钩子中传递给服务/模块

# 显式声明 __all__，控制 `from cf.core import *` 的行为，避免导出内部实现细节
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
