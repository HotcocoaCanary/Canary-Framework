"""Configuration — per-unit settings, parsed by pydantic-settings.

配置：框架只负责**作用域与装配**（哪个单元要哪份配置、从哪儿取到实例、怎么被替换），
解析、校验、类型转换全部交给 pydantic-settings。这条界限和日志那条是同一条：
框架做 scoping / identity / composition，不做 parsing / formatting / sinks。

单元通过**类级注解**声明自己要哪份配置，运行时装配时填进去::

    class RepoConfig(Config):
        model_config = SettingsConfigDict(env_prefix="REPO_")
        dsn: str
        timeout: float = 5.0

    @cocoa
    class Repository:
        config: RepoConfig          # 声明即注入，mypy 也认

        @on_start
        async def connect(self) -> None:
            await pool.open(self.config.dsn, timeout=self.config.timeout)

同一份配置类被多个单元声明时只构造一次，整图共享；测试里用
``Canary(App, overrides={RepoConfig: RepoConfig(dsn="sqlite://")})`` 替换，
与替换依赖单元是同一个机制。

取值优先级由 pydantic-settings 决定，默认即为：构造参数 > 环境变量 > ``.env`` >
secrets > 字段默认值。
"""

from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["CanaryConfig", "Config", "is_config"]


class Config(BaseSettings):
    """Base class for a unit's settings — a ``BaseSettings`` that also reads ``.env``.

    单元配置的基类。直接继承 ``pydantic_settings.BaseSettings`` 也一样能被注入，
    这个基类只是把 ``.env`` 和"忽略多余字段"这两个默认值先铺好。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class CanaryConfig(Config):
    """The framework's own settings, read from ``CANARY_*``.

    框架自有配置。``log_level`` 只作用在 ``canary`` 这一棵 logger 上，不装 handler、
    不设 format、不碰 root——那些属于应用的日志配置，框架不越界。留空（默认）时框架
    完全不干预日志级别，行为与标准库一致。
    """

    model_config = SettingsConfigDict(env_prefix="CANARY_", env_file=".env", extra="ignore")

    log_level: str | None = None


def is_config(annotation: Any) -> bool:
    """Whether *annotation* names a settings class the runtime should inject."""
    return isinstance(annotation, type) and issubclass(annotation, BaseSettings)
