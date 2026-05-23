"""@config 装饰器 —— 将普通类转换为 pydantic-settings BaseSettings 子类。

转换后的类自动读取环境变量和 .env 文件（内置 env_file=".env"）。
配置字段优先级: 环境变量 > .env 文件 > 默认值。

Usage:
    @config
    class AppConfig:
        host: str = "0.0.0.0"
        port: int = 8000
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


def config(cls: type) -> type:
    """将普通类转为 BaseSettings 子类，使其具备自动配置加载能力。

    动态创建逻辑:
        1. 提取原始类的 __annotations__ 作为 pydantic 的字段声明
        2. 提取原始类的类变量作为字段默认值
        3. SettingsConfigDict(env_file=".env") 让 pydantic-settings 自动读取 .env
        4. 用 type() 动态构造新类，保持原始类的 __name__ / __qualname__ / __module__

    参数可以是无括号装饰器 @config 或有括号 @config()，效果相同。
    """
    # 提取用户定义的类型注解（pydantic 按此推断字段类型和环境变量映射）
    annotations = getattr(cls, "__annotations__", {})

    settings_cls = type(
        cls.__name__,
        (BaseSettings,),
        {
            "__annotations__": annotations,
            # BaseSettings 的行为配置
            "model_config": SettingsConfigDict(
                env_file=".env",            # 自动从当前目录 .env 读取
                env_file_encoding="utf-8",
                extra="ignore",             # 忽略未声明的环境变量
                env_prefix="",              # 无前缀，字段名直接对应环境变量键
            ),
            # 将原始类的类变量（默认值）复制到新类
            **{
                k: v
                for k, v in vars(cls).items()
                if not k.startswith("__") and k != "__annotations__"
            },
        },
    )

    # 保持元信息一致，方便调试和日志
    settings_cls.__name__ = cls.__name__
    settings_cls.__qualname__ = cls.__qualname__
    settings_cls.__module__ = cls.__module__

    return settings_cls
