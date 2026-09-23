"""Canary: dependency injection and lifecycle for plain Python classes.

继承 ``Canary`` 即为最小单元，``dep(...)`` 声明依赖，三个阶段注解声明行为。启动一个
单元，它的依赖按依赖顺序就位::

    class Config(Canary):
        @init
        def load(self) -> None:
            self.dsn = os.environ["DSN"]

    class Database(Canary):
        config = dep(Config)

        @start
        async def connect(self) -> None:
            self.pool = await open_pool(self.config.dsn)

        @stop
        async def close(self) -> None:
            await self.pool.close()

    class UserService(Canary):
        db = dep(Database)

    async with UserService() as service:     # Config -> Database -> UserService
        ...                                  # 退出时逆序回收

公开 API 全部从本模块导出，详见 :mod:`canary_framework.core`。
"""

from __future__ import annotations

__version__ = "1.1.0"

from canary_framework.core import (
    Canary,
    CanaryError,
    CircularDependencyError,
    ConstructionError,
    DeclarationError,
    LifecycleError,
    Phase,
    Scope,
    dep,
    deps_of,
    enter,
    init,
    leave,
    scope_of,
    start,
    stop,
)

__all__ = [
    "Canary",
    "CanaryError",
    "CircularDependencyError",
    "ConstructionError",
    "DeclarationError",
    "LifecycleError",
    "Phase",
    "Scope",
    "dep",
    "deps_of",
    "enter",
    "init",
    "leave",
    "scope_of",
    "start",
    "stop",
]
