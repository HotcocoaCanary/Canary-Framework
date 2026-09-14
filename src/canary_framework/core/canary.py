"""The unit base class and the dependency declaration function.

单元基类与依赖声明函数。继承 :class:`Canary` 即为一个单元，用 :func:`dep` 声明它依赖谁，
用 ``@init`` / ``@start`` / ``@stop`` 声明它在各阶段的行为。

单元仍是普通 Python 类，可以继承、混入、嵌套，也可以覆盖本类的方法并以 ``super()`` 组合。
本模块是唯一同时依赖声明层与运行层的地方，其余模块的依赖方向严格单向。
"""

from __future__ import annotations

import types
from typing import Literal, Self

from canary_framework.core.declare.dep import Dep
from canary_framework.core.declare.phase import init as init_phase
from canary_framework.core.declare.phase import start as start_phase
from canary_framework.core.declare.phase import stop as stop_phase
from canary_framework.core.errors import DeclarationError
from canary_framework.core.runtime.advance import advance
from canary_framework.core.runtime.scope import Scope, scope_of
from canary_framework.core.runtime.unwind import unwind


class Canary:
    """A unit: it declares what it depends on, and it can run its own lifecycle.

    最小单元::

        class Database(Canary):
            config = dep(Config)

            @start
            async def connect(self) -> None:
                self.pool = await open_pool(self.config.dsn)

            @stop
            async def close(self) -> None:
                await self.pool.close()

    启动一个单元，它的依赖按依赖顺序就位；退出时逆序回收::

        async with UserService() as service:
            ...

    四个动作一一对应：无参构造、:meth:`init`、:meth:`start`、:meth:`stop`。

    :meth:`init` 与 :meth:`start` 是单元的动作，沿依赖向下推进；:meth:`stop` 是图的动作，
    回收整个作用域的台账，在图中任一单元上调用效果相同。
    """

    #: 所在作用域。第一次进入生命周期时创建，之后不变；同一张图上的单元共享同一个。
    _canary_scope: Scope | None = None

    async def init(self) -> None:
        """Run every ``@init`` across this unit's graph, dependencies first.

        推进 ``init``：先初始化全部依赖，再运行自身的 ``@init``。本方法的返回是一道栅栏，
        在调用 :meth:`start` 之前没有任何单元开始运行。
        """
        await advance(self, init_phase)

    async def start(self) -> None:
        """Run every ``@start`` across this unit's graph, dependencies first.

        推进 ``start``：先启动全部依赖，再运行自身的 ``@start``。单元进入该阶段即记账，
        :meth:`stop` 按台账回收。

        :raises LifecycleError: 尚未调用过 :meth:`init`。
        """
        await advance(self, start_phase)

    async def stop(self) -> None:
        """Reclaim everything that entered ``start``, in reverse order.

        按台账逆序执行 ``@stop``。这是唯一的回收路径，正常结束与失败结束共用；重复调用
        幂等，从未启动时为空操作。

        :raises ExceptionGroup: 一个或多个 ``@stop`` 抛出异常，即使只有一个。
        """
        errors = await unwind(scope_of(self), stop_phase, undoing=start_phase)
        if errors:
            raise ExceptionGroup(f"{len(errors)} error(s) while stopping", errors)

    async def __aenter__(self) -> Self:
        """Run ``init`` then ``start``, reclaiming what started if either fails.

        依次调用 :meth:`init` 与 :meth:`start`。三个动作都经由本类的方法，因此子类的
        覆盖在此同样生效。任一环节失败时回收已启动的单元并原样抛出最初的异常；回收本身
        再失败时，作为 note 附在该异常上。
        """
        try:
            await self.init()
            await self.start()
        except BaseException as exc:
            try:
                await self.stop()
            except BaseException as during_rollback:
                exc.add_note(f"during rollback: {during_rollback!r}")
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> Literal[False]:
        """Reclaim the graph on exit, never suppressing the exception.

        退出时回收整张图，不吞掉任何异常。
        """
        await self.stop()
        return False


def dep[T: Canary](cls: type[T]) -> T:
    """Declare a dependency on *cls*.

    声明一条依赖。返回值标注为 ``T``，因此 ``db = dep(Database)`` 直接推断为
    ``Database``，无需另写注解；属性名由使用者决定，与被依赖的类名无关::

        class AlertDispatcher(Canary):
            sink = dep(LoggingAlertSink)

    :param cls: 被依赖的单元类型。
    :raises DeclarationError: *cls* 不是 :class:`Canary` 的子类。该检查在类体求值时进行，
        错误指向写下 ``dep(...)`` 的那一行。
    """
    if not (isinstance(cls, type) and issubclass(cls, Canary)):
        raise DeclarationError(f"dep({cls!r}): not a Canary subclass")
    return Dep(cls)  # type: ignore[return-value]
