"""Framework exceptions — all inherit :class:`CanaryError`.

框架异常：全部继承 :class:`CanaryError`，便于一次 ``except`` 兜底。扩展包
（web / agent / …）的错误也应继承 :class:`CanaryError`，这样用户
``except CanaryError`` 就能统一捕获框架与所有扩展的错误。
"""

from typing import Self


class CanaryError(Exception):
    """Base class for every framework error — and the extension point.

    框架与扩展包所有错误的根基类。扩展包先定义自己的子基类（如 ``WebError``），
    再派生具体错误，即可与核心错误统一捕获。
    """


class CircularDependencyError(CanaryError):
    """Raised when the dependency graph contains a cycle.

    依赖图成环时抛出；``cycle`` 记录环上各类型的名字。
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__("circular dependency detected: " + " -> ".join(cycle))


class LifecycleError(CanaryError):
    """Raised on an illegal lifecycle transition.

    生命周期非法跳转时抛出（例如未初始化就 ``stop``）。
    """


class InjectionError(CanaryError):
    """Raised when two things claim the same attribute name on one unit.

    两个来源抢同一个属性名时抛出（例如 ``KBFileRepository`` 与 ``KbFileRepository``
    的 snake_case 同名，或依赖名撞上配置/日志的注解名）。旧版是"后写的赢"，
    静默覆盖掉一个依赖——这类错误必须响。
    """

    def __init__(self, unit: str, attribute: str, claimants: list[str]) -> None:
        self.unit = unit
        self.attribute = attribute
        self.claimants = claimants
        super().__init__(
            f"{unit}.{attribute} is claimed by more than one source: " + ", ".join(claimants)
        )


class ConstructionError(CanaryError):
    """Raised when the runtime cannot construct a unit because it needs arguments.

    单元由框架**无参构造**（``build_graph`` 里的 ``t()``），所以带必填参数的类不能
    直接进图。这条约束一直存在，只是从前失败时抛的是构造器自己的 ``TypeError``，
    既不指向这条规则、也兜不进 ``except CanaryError``。
    """

    def __init__(self, unit: str, detail: str) -> None:
        self.unit = unit
        super().__init__(
            f"cannot construct {unit}: {detail}. Units are constructed with no arguments — "
            f"either take the value from a dependency in @on_init/@on_start, or build it "
            f"yourself and hand it over: Canary(root, provide={{{unit}: {unit}(...)}})."
        )


class ProvisionError(CanaryError):
    """Raised when an entry passed to ``Canary(provide=...)`` cannot be honoured.

    ``provide`` 只有一条规则：**给出的实例是完整的**——框架不构造它、不展开它声明的
    依赖、也不往它里面注入任何东西。两种违背这条规则的写法都在装配阶段抛出：

    - **条目没落到图上**（类型写错）。沉默地忽略会让测试"通过"却根本没替换成功，
      也会让生产接线以为自己接上了。
    - **给出的实例自己还声明着** ``deps``。那些依赖不会被装配，属性也就永远不会出现。
      从前这里漏出一个裸 ``KeyError``，而且漏不漏取决于别的单元有没有恰好依赖同一个
      类型——同一份代码两种行为，这比报错本身更糟。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

    @classmethod
    def never_applied(cls, unused: list[str]) -> Self:
        return cls(
            "provided types never applied (not reachable from the roots): " + ", ".join(unused)
        )

    @classmethod
    def declares_dependencies(cls, unit: str, declared: list[str]) -> Self:
        return cls(
            f"{unit} was handed to provide=, but it still declares dependencies: "
            + ", ".join(declared)
            + ". A provided instance is complete — Canary neither constructs it nor wires "
            "anything into it, so those attributes would never appear. Either drop the "
            "declaration (a substitute can be a plain class, or @cocoa with no deps), or "
            "build its collaborators yourself and pass them to its constructor."
        )
