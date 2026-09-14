"""The shared state of one run.

作用域：一次运行共享的全部状态，包括实例表、推进记录与逐阶段的台账。同一张图上的单元
共享同一个作用域，因此"每个类型一个实例"由它保证。
"""

from __future__ import annotations

import inspect
from asyncio import Future
from collections import defaultdict

from canary_framework.core.declare.dep import SCOPE
from canary_framework.core.errors import ConstructionError


class Scope:
    """The instances, phase records and ledgers shared by one run.

    一次运行共享的状态。
    """

    __slots__ = ("entered", "instances", "phases")

    def __init__(self) -> None:
        #: 类型到共享实例。
        self.instances: dict[type, object] = {}
        #: (类型, 阶段名) 到该次推进本身。键不存在表示未开始，未完成表示进行中，
        #: 已完成表示推进结束。
        self.phases: dict[tuple[type, str], Future[None]] = {}
        #: 阶段名到进入该阶段的单元，按进入顺序排列，回收时逆序消费。
        self.entered: dict[str, list[object]] = defaultdict(list)

    def instance(self, cls: type) -> object:
        """Return the single instance of *cls* in this scope, constructing it on first use.

        返回 *cls* 在本作用域内的唯一实例。首次取用时无参构造并登记作用域。
        """
        unit = self.instances.get(cls)
        if unit is None:
            unit = _construct(cls)
            self.adopt(unit)
        return unit

    def adopt(self, unit: object) -> None:
        """Register *unit* as this scope's instance of its own type.

        把 *unit* 登记为本作用域内该类型的实例，并把作用域写到它身上。
        """
        setattr(unit, SCOPE, self)
        self.instances.setdefault(type(unit), unit)


def scope_of(unit: object) -> Scope:
    """Return the scope *unit* belongs to, creating one if it has none.

    返回单元所在的作用域。由使用者自行构造的根单元在第一次取用时得到一个新作用域，
    并被登记进去。
    """
    scope = getattr(unit, SCOPE, None)
    if scope is None:
        scope = Scope()
        scope.adopt(unit)
    return scope


def _construct(cls: type) -> object:
    """Instantiate *cls* with no arguments, turning an arity mismatch into a framework error.

    先行调用，出现 ``TypeError`` 后再检查签名，因此 ``inspect.signature`` 只在失败路径上
    执行。检查签名用于区分两种 ``TypeError``：签名无法无参调用时抛
    :class:`ConstructionError`，构造器自身抛出的则原样传播。
    """
    try:
        return cls()
    except TypeError as exc:
        detail = _arity_problem(cls)
        if detail is None:
            raise
        raise ConstructionError(cls, detail) from exc


def _arity_problem(cls: type) -> str | None:
    """Explain why *cls* cannot be called with no arguments, or return ``None`` if it can.

    返回无参调用不成立的原因；可以无参调用，或取不到签名（内建与 C 扩展类型）时返回
    ``None``。
    """
    try:
        signature = inspect.signature(cls)
    except (TypeError, ValueError):
        return None
    try:
        signature.bind()
    except TypeError as exc:
        return str(exc)
    return None
