"""The core: one base class, three phase decorators, and the engine that runs them.

核心。声明与解释分开，依赖方向严格单向：``canary -> runtime -> declare -> errors``。

- :class:`Canary` 是单元，:func:`dep` 声明它依赖谁。
- ``@init`` / ``@start`` / ``@stop`` 标记单元在各阶段的行为。
- :func:`advance` 在依赖图上推进一个阶段，:func:`unwind` 按台账逆序回收。

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
from canary_framework.core.declare.introspect import deps_of
from canary_framework.core.declare.phase import Phase, init, start, stop
from canary_framework.core.errors import (
    CanaryError,
    CircularDependencyError,
    ConstructionError,
    DeclarationError,
    LifecycleError,
)
from canary_framework.core.runtime.advance import advance
from canary_framework.core.runtime.scope import Scope, scope_of
from canary_framework.core.runtime.unwind import unwind

__all__ = [
    "Canary",
    "CanaryError",
    "CircularDependencyError",
    "ConstructionError",
    "DeclarationError",
    "LifecycleError",
    "Phase",
    "Scope",
    "advance",
    "dep",
    "deps_of",
    "init",
    "scope_of",
    "start",
    "stop",
    "unwind",
]
