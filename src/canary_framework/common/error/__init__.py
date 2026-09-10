"""Framework exceptions — all inherit :class:`CanaryError`.

框架异常：全部继承 :class:`CanaryError`，可用一次 ``except CanaryError`` 统一捕获。
"""


class CanaryError(Exception):
    """Base class for every framework error.

    框架所有错误的根基类。扩展可先定义自己的子基类，再派生具体错误。
    """


class CircularDependencyError(CanaryError):
    """Raised when the dependency graph contains a cycle.

    依赖图成环时抛出。

    :ivar cycle: 环上各类型的名字。
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__("circular dependency detected: " + " -> ".join(cycle))


class LifecycleError(CanaryError):
    """Raised on an illegal lifecycle transition.

    生命周期非法跳转时抛出，例如未 ``init()`` 就 ``start()``、或重复 ``start()``。
    """


class InjectionError(CanaryError):
    """Raised when two dependencies claim the same attribute name on one unit.

    两个依赖的 snake_case 属性名相同时抛出（如 ``KBFileRepository`` 与
    ``KbFileRepository`` 同为 ``kb_file_repository``）。改名其中一个类即可。

    :ivar unit: 发生冲突的单元名。
    :ivar attribute: 被争抢的属性名。
    :ivar claimants: 争抢该属性的依赖类名。
    """

    def __init__(self, unit: str, attribute: str, claimants: list[str]) -> None:
        self.unit = unit
        self.attribute = attribute
        self.claimants = claimants
        super().__init__(
            f"{unit}.{attribute} is claimed by more than one source: " + ", ".join(claimants)
        )


class ConstructionError(CanaryError):
    """Raised when a unit cannot be constructed because it needs arguments.

    单元一律由框架无参构造，带必填参数的类因此不能进图。出路是把构造参数变成依赖：
    在 ``@cocoa(deps=[...])`` 里声明协作者，在 ``@on_init`` 或 ``@on_start`` 里从它们
    读取所需的值。

    :ivar unit: 无法构造的单元名。
    """

    def __init__(self, unit: str, detail: str) -> None:
        self.unit = unit
        super().__init__(
            f"cannot construct {unit}: {detail}. Units are always constructed with no "
            f"arguments — declare what it needs in @cocoa(deps=[...]) and read the values "
            f"from those dependencies in @on_init or @on_start."
        )
