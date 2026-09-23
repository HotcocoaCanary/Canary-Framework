"""The core: one base class, three phase decorators, and the engine that runs them.

核心。声明与解释分开，依赖方向严格单向：``canary -> flow -> meta -> errors``。

- :class:`Canary` 是单元，:func:`dep` 声明它依赖谁。
- ``@init`` / ``@start`` / ``@stop`` 标记单元在各阶段的行为。
- :func:`enter` 在依赖图上进入一个阶段，依赖在前；:func:`leave` 离开一个阶段，本单元在前。

::

    class Database(Canary):
        config = dep(Config)

        @start
        async def connect(self) -> None: ...

        @stop
        async def close(self) -> None: ...

    async with UserService() as service:
        ...
"""

from canary_framework.core.canary import Canary, dep
from canary_framework.core.errors import (
    CanaryError,
    CircularDependencyError,
    ConstructionError,
    DeclarationError,
    LifecycleError,
)
from canary_framework.core.flow.enter import enter
from canary_framework.core.flow.leave import leave
from canary_framework.core.flow.scope import Scope, scope_of
from canary_framework.core.meta.introspect import deps_of
from canary_framework.core.meta.phase import Phase, init, start, stop

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
