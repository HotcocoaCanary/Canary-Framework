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
