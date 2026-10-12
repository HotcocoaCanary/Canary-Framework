"""The settings base class.

配置基类。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from canary_framework.core import Canary, dep

#: ``dep()`` 返回的描述符类型。核心没有公开导出它，这里从公开的 ``dep()`` 取得。
_DEP = type(dep(Canary))


class Settings(BaseSettings, Canary):
    """A pydantic ``BaseSettings`` that is also a unit.

    既是 pydantic 的 ``BaseSettings``，也是图上的一个单元::

        class AppConfig(Settings):
            model_config = SettingsConfigDict(env_file=".env")

            dsn: str = "sqlite://"
            log_level: str = "INFO"

        class Database(Canary):
            config = dep(AppConfig)

            @start
            async def connect(self) -> None:
                self.pool = await open_pool(self.config.dsn)

    ``BaseSettings`` 负责读环境变量与 ``.env``，用法与 pydantic-settings 完全一致；
    ``Canary`` 让它成为图上的节点：谁要用谁写 ``dep(AppConfig)``，整张图共享同一个实例。
    它可以有自己的依赖与钩子：``dep()`` 写在模型里不会被当成字段，这是本类唯一替 pydantic
    做的配置（``ignored_types``），子类的 ``model_config`` 与它合并。

    框架无参构造它，因此每个字段都要能从默认值或环境中取到。测试里换一份配置用
    ``Scope.provide``::

        scope_of(service).provide(AppConfig, AppConfig(dsn="sqlite://:memory:"))

    字段不能叫 ``init`` / ``start`` / ``stop``，它们是单元的方法。
    """

    model_config = SettingsConfigDict(ignored_types=(_DEP,))
