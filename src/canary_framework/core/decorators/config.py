"""Configuration decorator — converts plain classes to pydantic-settings models.

设计思路 (Design rationale):
    为什么使用动态 ``type()`` 构造而不是让用户直接继承 ``BaseSettings``？
    （Why ``type()`` instead of direct ``BaseSettings`` inheritance?）

    1. **零侵入**：用户只需写普通 Python 类，无需了解 pydantic
       Non-invasive: users write plain Python classes, no pydantic knowledge needed.
    2. **统一入口**：所有配置通过 ``@config`` 装饰，框架可以在此处统一注入
       ``SettingsConfigDict``（``env_file=".env"``、``extra="ignore"`` 等）
       Single entry point: inject settings consistently without user repetition.
    3. **可替换性**：未来如果要替换 pydantic 为其他配置库，只需改这一个文件
       Future-proof: swap the config backend by editing one file.

动态类构造流程 (Dynamic class construction flow):
    1. 提取原始类的 ``__annotations__`` 作为 pydantic 字段声明
    2. 提取类变量作为默认值（过滤掉 ``__dunder__`` 和 ``__annotations__``）
    3. 注入 ``SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="")``
    4. 保持 ``__name__`` / ``__qualname__`` / ``__module__`` 不变，方便调试

优先级 (Priority): 环境变量 > .env 文件 > 类默认值
"""

from __future__ import annotations

from typing import TypeVar

from pydantic_settings import BaseSettings, SettingsConfigDict

_C = TypeVar("_C", bound=type)


def config(cls: _C) -> type:  # noqa: UP047
    """Convert a plain class into a :class:`~pydantic_settings.BaseSettings` subclass.

    将普通 Python 类转换为 pydantic-settings 子类，使其自动从环境变量和
    ``.env`` 文件加载配置。

    Args:
        cls: 带类型注解和可选默认值的普通类。
             A class with type-annotated fields and optional defaults.

    Returns:
        一个新的类，继承自 :class:`BaseSettings`，行为与原类一致外加环境变量加载。
        A new class inheriting from :class:`BaseSettings`.

    Example::

        @config
        class AppConfig:
            host: str = "127.0.0.1"
            port: int = 8000

        cfg = AppConfig()
        assert cfg.host == "127.0.0.1"  # or from env var HOST

    .. note::
        ``.env`` 文件路径硬编码为 ``"env_file=.env"``（相对于当前工作目录）。
        对于需要自定义路径的场景，目前需要在子类中覆盖
        :attr:`model_config <pydantic_settings.BaseSettings.model_config>`。
    """
    annotations = getattr(cls, "__annotations__", {})

    # 动态构造新类，继承 BaseSettings
    # Dynamically build a new class inheriting from BaseSettings
    base: type = type(
        cls.__name__,
        (BaseSettings,),
        {
            "__annotations__": annotations,
            "model_config": SettingsConfigDict(
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",  # 忽略未声明的环境变量，避免意外注入
                env_prefix="",  # 无前缀：字段名直接映射环境变量名
            ),
            # 复制原始类的类变量作为默认值
            # Copy class-level variables as default values
            **{
                k: v
                for k, v in vars(cls).items()
                if not k.startswith("__") and k != "__annotations__"
            },
        },
    )

    # 保持元信息一致，方便调试和日志
    # Preserve original metadata for debugging and logging
    base.__name__ = cls.__name__
    base.__qualname__ = cls.__qualname__
    base.__module__ = cls.__module__

    return base
