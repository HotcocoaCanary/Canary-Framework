"""The shared state of one run.

作用域：一次运行共享的全部状态——实例表、依赖图，以及每个单元在每个阶段上的状态。同一张
图上的单元共享同一个作用域，因此"每个类型一个实例"由它保证。
"""

from __future__ import annotations

import enum
import inspect
from asyncio import Future
from dataclasses import dataclass

from canary_framework.core.errors import ConstructionError, LifecycleError
from canary_framework.core.meta.dep import SCOPE
from canary_framework.core.meta.phase import Phase


class State(enum.Enum):
    """Where a unit stands in one phase.

    一个单元在一个阶段上的状态。
    """

    #: 未进入，或已离开。
    IDLE = enum.auto()
    #: 已被一次 enter 认领：在等依赖，或正在运行钩子。
    ENTERING = enum.auto()
    #: 钩子全部成功。
    ENTERED = enum.auto()
    #: 进入失败或被取消，尚未离开。阶段声明了 ``leave`` 时，失败的单元随即离开。
    FAILED = enum.auto()
    #: 正在运行离开钩子。此时它仍在使用自己的依赖。
    LEAVING = enum.auto()


#: 这些状态下，单元正在使用、或还可能使用它的依赖。
IN_USE = frozenset({State.ENTERING, State.ENTERED, State.FAILED, State.LEAVING})


@dataclass(slots=True)
class Track:
    """One unit's standing in one phase.

    一个单元在一个阶段上的记录。
    """

    state: State = State.IDLE
    #: 进入钩子开始后的单元本身；离开钩子运行时取走。不为 ``None`` 即持有该阶段获取的东西。
    unit: object | None = None
    #: 本次进入的结果，依赖者等待它：成功、失败或取消。
    outcome: Future[None] | None = None
    #: 进行中的一次离开（含递归尝试依赖），同时离开同一个单元时后到者等待它。
    leaving: Future[None] | None = None

    def reset(self) -> None:
        """Return to idle. A leave still carrying on to the dependencies stays recorded.

        回到空闲。仍在递归尝试依赖的那次离开保留，以便后到者等待。
        """
        self.state = State.IDLE
        self.unit = None
        self.outcome = None


class Scope:
    """The instances, the dependency graph and every unit's state in every phase.

    一次运行共享的状态。
    """

    __slots__ = ("dependents", "graph", "instances", "keys", "known", "tracks")

    def __init__(self) -> None:
        #: 类型到共享实例。经 :meth:`provide` 登记的实例可以是该类型的子类实例。
        self.instances: dict[type, object] = {}
        #: 实例的 ``id`` 到它登记的类型，:meth:`key_of` 据此查找。
        self.keys: dict[int, type] = {}
        #: 依赖图：键到它依赖的键。插入顺序是拓扑序（依赖在前），见 ``flow.graph``。
        self.graph: dict[type, tuple[type, ...]] = {}
        #: 依赖图的反向边：键到依赖它的键。
        self.dependents: dict[type, list[type]] = {}
        #: (键, 阶段名) 到该单元在该阶段上的记录。
        self.tracks: dict[tuple[type, str], Track] = {}
        #: 阶段名到在本作用域进入过的阶段，离开时据此找出以它为前驱的阶段。
        self.known: dict[str, Phase] = {}

    def track(self, cls: type, phase: Phase) -> Track:
        """Return *cls*'s record for *phase*, creating an idle one on first use.

        返回 *cls* 在 *phase* 上的记录，首次取用时为空闲。
        """
        key = (cls, phase.name)
        if (found := self.tracks.get(key)) is None:
            found = self.tracks[key] = Track()
        return found

    def entered(self, phase: Phase) -> dict[type, object]:
        """Return the units holding what *phase* acquired, dependencies first.

        返回持有 *phase* 所获取东西的单元：进入钩子开始后、离开之前。依赖在前。
        """
        return {
            cls: track.unit
            for (cls, name), track in self.tracks.items()
            if name == phase.name and track.unit is not None
        }

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
        if self.instances.setdefault(type(unit), unit) is unit:
            self.keys[id(unit)] = type(unit)

    def provide[T](self, cls: type[T], unit: T) -> None:
        """Make *unit* this scope's instance of *cls*, before anything constructs one.

        把 *unit* 登记为本作用域内 *cls* 的实例。之后图中所有 ``dep(cls)`` 都取回它，它按
        自身的类型参与生命周期：运行自己的钩子，进入自己声明的依赖。用于测试替身，或把
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
        if cls in self.instances or cls in self.graph:
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
        self.keys[id(unit)] = cls

    def key_of(self, unit: object) -> type:
        """Return the type *unit* is registered under in this scope.

        返回 *unit* 在本作用域内登记的键。经 :meth:`provide` 登记的替身，键是被替换的类型
        而不是它自身的类型；未登记时返回它自身的类型。
        """
        return self.keys.get(id(unit), type(unit))

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
