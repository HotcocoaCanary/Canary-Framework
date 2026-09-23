"""The shared state of one run.

作用域：一次运行共享的全部状态，包括实例表、推进记录与逐阶段的台账。同一张图上的单元
共享同一个作用域，因此"每个类型一个实例"由它保证。
"""

from __future__ import annotations

import inspect
from asyncio import Future
from collections import defaultdict

from canary_framework.core.errors import ConstructionError, LifecycleError
from canary_framework.core.meta.dep import SCOPE
from canary_framework.core.meta.phase import Phase


class Scope:
    """The instances, phase records and ledgers shared by one run.

    一次运行共享的状态。
    """

    __slots__ = ("entered", "instances", "known", "phases")

    def __init__(self) -> None:
        #: 类型到共享实例。经 :meth:`provide` 登记的实例可以是该类型的子类实例。
        self.instances: dict[type, object] = {}
        #: (类型, 阶段名) 到该次推进本身。键不存在表示未开始或已被撤销，未完成表示进行中，
        #: 已完成表示推进结束。失败或取消的记录在运行它的 advance() 返回时清除，因此可以重试。
        self.phases: dict[tuple[type, str], Future[None]] = {}
        #: 阶段名到进入该阶段的单元，以类型为键、按进入顺序排列，回收时逆序消费。同一个
        #: 类型重复进入时只保留最后一次的位置，因此台账里不会出现重复。
        self.entered: dict[str, dict[type, object]] = defaultdict(dict)
        #: 阶段名到在本作用域推进过的阶段对象，回收时据此找出以被撤销阶段为前驱的阶段。
        self.known: dict[str, Phase] = {}

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

    def provide[T](self, cls: type[T], unit: T) -> None:
        """Make *unit* this scope's instance of *cls*, before anything constructs one.

        把 *unit* 登记为本作用域内 *cls* 的实例。之后图中所有 ``dep(cls)`` 都取回它，它按
        自身的类型参与生命周期：运行自己的钩子，推进自己声明的依赖。用于测试替身，或把
        依赖替换为预先配置好的实例::

            service = UserService()
            scope_of(service).provide(Database, FakeDatabase())
            async with service:
                ...

        :raises TypeError: *unit* 不是 *cls* 的实例。
        :raises LifecycleError: 本作用域已经有 *cls* 的实例，或 *unit* 已属于另一个作用域。
        """
        if not isinstance(unit, cls):
            raise TypeError(f"provide({cls.__name__}, ...): {unit!r} is not a {cls.__name__}")
        if cls in self.instances:
            raise LifecycleError(
                f"provide({cls.__name__}, ...): this scope already has a {cls.__name__}. "
                f"Provide replacements before the lifecycle begins."
            )
        owner = getattr(unit, SCOPE, None)
        if owner is not None and owner is not self:
            raise LifecycleError(
                f"provide({cls.__name__}, ...): {type(unit).__name__} already belongs to another scope"
            )
        setattr(unit, SCOPE, self)
        self.instances[cls] = unit

    def resolve(self, cls: type) -> type:
        """Return the type that will stand in for *cls*: a provided unit's own type, or *cls*.

        返回 *cls* 在本作用域内的实际类型。经 :meth:`provide` 登记过时为登记实例的类型，
        否则为 *cls* 本身。只读取，不构造。
        """
        unit = self.instances.get(cls)
        return cls if unit is None else type(unit)


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
