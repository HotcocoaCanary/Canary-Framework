"""Settings as a unit.

配置。需要 ``pydantic-settings``：``pip install canary-framework[config]``::

    class AppConfig(Settings):
        dsn: str = "sqlite://"

    class Database(Canary):
        config = dep(AppConfig)

:class:`Settings` 同时是 pydantic 的 ``BaseSettings`` 与一个单元，除此之外没有别的内容。
"""

from canary_framework.config.settings import Settings

__all__ = ["Settings"]
