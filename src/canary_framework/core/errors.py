"""Framework exceptions.

框架异常。全部继承 :class:`CanaryError`，因此可用一次 ``except CanaryError`` 统一捕获。
"""

from __future__ import annotations


class CanaryError(Exception):
    """Base class for every framework error.

    框架所有错误的基类。
    """


class DeclarationError(CanaryError):
    """Raised at declaration time, when a class or a dependency is malformed.

    声明期错误。在 ``dep(...)`` 求值的那一刻抛出，不必等到运行。
    """


class ConstructionError(CanaryError):
    """Raised when a unit cannot be constructed because it requires arguments.

    单元一律由框架无参构造，带必填参数的类因此无法进入依赖图。解决方式是把构造参数
    改写成依赖：用 ``dep(...)`` 声明协作者，在 ``@init`` 或 ``@start`` 中从协作者读取
    所需的值。

    :ivar unit: 无法构造的单元。
    """

    def __init__(self, unit: type, detail: str) -> None:
        self.unit = unit
        super().__init__(
            f"cannot construct {unit.__name__}: {detail}. Units are always constructed with "
            f"no arguments. Declare what it needs with dep(...) and read the values from "
            f"those dependencies in @init or @start."
        )


class CircularDependencyError(CanaryError):
    """Raised when the dependency graph contains a cycle.

    依赖成环时抛出。携带的是构建依赖图时走到环上的路径，首尾为同一个类型。

    :ivar cycle: 环上的类型，按经过顺序排列。
    """

    def __init__(self, cycle: tuple[type, ...]) -> None:
        self.cycle = cycle
        super().__init__("circular dependency: " + " -> ".join(t.__name__ for t in cycle))


class LifecycleError(CanaryError):
    """Raised when a unit is used outside its lifecycle.

    在生命周期之外使用单元时抛出。例如尚未进入任何阶段就读取依赖，或在前驱阶段
    尚未进入时进入某个阶段。
    """
