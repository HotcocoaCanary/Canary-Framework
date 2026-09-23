"""Lifecycle phases.

阶段：一个生命周期阶段，同时是标记该阶段钩子的装饰器。框架提供 ``init`` / ``start`` /
``stop`` 三个；``Phase("migrate")`` 即可得到第四个，无需注册。
"""

from __future__ import annotations

from collections.abc import Callable

#: 写在方法上的标记：该方法属于哪些阶段，值为阶段名的元组。
PHASES = "__canary_phases__"


class Phase:
    """A lifecycle stage, and the decorator that marks its hooks.

    阶段对象可调用，调用的效果是给方法打上本阶段的标记::

        @start
        async def connect(self) -> None: ...

    同一个方法可以属于多个阶段，同一个类的同一个阶段可以有多个方法。

    :param name: 阶段名。作用域以它为键记录每个单元在该阶段上的状态。
    :param after: 前驱阶段。声明之后，本阶段在某个单元上运行之前，该单元的前驱阶段
        必须已经完成，否则抛出 :class:`LifecycleError`。
    :param leave: 离开本阶段时运行的阶段。本阶段的钩子获取的东西由它的钩子释放：``leave()``
        运行它们；一个单元在本阶段失败或被取消时也立即运行它们。``start`` 的 *leave* 是
        ``stop``。
    """

    __slots__ = ("after", "leave", "name")

    def __init__(
        self, name: str, *, after: Phase | None = None, leave: Phase | None = None
    ) -> None:
        self.name = name
        self.after = after
        self.leave = leave

    def __call__[F: Callable[..., object]](self, fn: F) -> F:
        """Mark *fn* as a hook of this phase, and return it unchanged.

        给 *fn* 打上本阶段的标记，原样返回。
        """
        setattr(fn, PHASES, (*getattr(fn, PHASES, ()), self.name))
        return fn

    def __repr__(self) -> str:
        return f"@{self.name}"


init = Phase("init")
stop = Phase("stop")
start = Phase("start", after=init, leave=stop)
