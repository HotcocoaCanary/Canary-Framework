"""Framework exceptions — all inherit :class:`CanaryError`.

框架异常：全部继承 :class:`CanaryError`，便于一次 ``except`` 兜底。扩展包
（web / agent / …）的错误也应继承 :class:`CanaryError`，这样用户
``except CanaryError`` 就能统一捕获框架与所有扩展的错误。
"""


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

    单元一律由框架**无参构造**，所以带必填参数的类不能进图。

    这条约束是有意的，不是限制。构造函数没有对手——``@on_start`` 有 ``@on_stop`` 配对，
    而"构造"没有"析构"：一个在 ``__init__`` 里开了连接的单元，如果后面某个单元构造失败，
    没有任何机制去关它。把需要外界输入的事情推迟到生命周期钩子里，等于让每一件事都落进
    一个有台账、能逆序回收的阶段。``__init__`` 也不能是 ``async``，本来就装不下需要 IO
    的初始化。

    所以出路只有一条：**把构造参数变成依赖**。值从协作者那里读（``self.config.url``），
    读取动作放在 ``@on_init``（只要依赖，不碰外部资源）或 ``@on_start``（要连接、要起
    后台任务）里。
    """

    def __init__(self, unit: str, detail: str) -> None:
        self.unit = unit
        super().__init__(
            f"cannot construct {unit}: {detail}. Units are always constructed with no "
            f"arguments — declare what it needs in @cocoa(deps=[...]) and read the values "
            f"from those dependencies in @on_init or @on_start."
        )
