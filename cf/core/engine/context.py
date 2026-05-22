"""
上下文 —— 在 @on_init 钩子中传递给服务/模块的通用上下文对象。

模块即服务，两者使用完全相同的上下文。
唯一入口是 ctx.config，服务通过它访问由 @config 声明的配置对象。
"""
from __future__ import annotations


class Context:
    """
    传给 @on_init 钩子的上下文对象。服务和模块通用。

    属性：
        config: 由 pydantic-settings 从 .env 文件和环境变量加载的配置对象
    """

    def __init__(self, config_instance: object | None = None) -> None:
        self._config = config_instance

    @property
    def config(self) -> object:
        if self._config is None:
            raise RuntimeError("No config bound to this service/module.")
        return self._config
