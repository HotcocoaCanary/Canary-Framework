"""Dependency declaration.

依赖声明。描述符持有的是类对象本身而非名字，因此无需求值，不受
``from __future__ import annotations``、``if TYPE_CHECKING`` 或函数作用域的影响。

对外的声明入口是 :func:`~canary_framework.core.canary.dep`，与 :class:`Canary` 同在
一个模块。
"""

from __future__ import annotations

from canary_framework.core.errors import LifecycleError

#: 写在实例上的标记：该实例所在的作用域。属性名在此定义，:class:`Scope` 与
#: :class:`Canary` 均从此处取用。
SCOPE = "_canary_scope"


class Dep[T]:
    """One declared dependency, resolved from the owner's scope on access.

    一条依赖声明。读取时从宿主所在的作用域取回共享实例。属性名由使用者决定，与被依赖的
    类名无关。

    描述符只读取作用域，不创建作用域：生命周期尚未开始时读取会抛
    :class:`LifecycleError`，而不是另建一张图。

    依赖不可赋值：赋值只会改到宿主的这一个属性，替换无法在整张图上生效。替换依赖用
    :meth:`Scope.provide <canary_framework.core.flow.scope.Scope.provide>`。
    """

    __slots__ = ("cls", "name")

    def __init__(self, cls: type[T]) -> None:
        self.cls = cls
        self.name = "<unnamed>"

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: object | None, owner: type | None = None) -> T:
        if obj is None:
            return self  # type: ignore[return-value]
        scope = getattr(obj, SCOPE, None)
        if scope is None:
            raise LifecycleError(
                f"{type(obj).__name__}.{self.name} is unavailable before the lifecycle begins. "
                f"Dependencies exist from @init onward, not in __init__."
            )
        return scope.instance(self.cls)  # type: ignore[no-any-return]

    def __set__(self, obj: object, value: object) -> None:
        # 赋值只会改到这一个属性，图中其余单元仍取回原来的实例，替换因此无法生效。
        raise AttributeError(
            f"{type(obj).__name__}.{self.name} is a dependency and cannot be assigned. "
            f"To replace {self.cls.__name__} across the graph, call "
            f"scope_of(root).provide({self.cls.__name__}, replacement) before the lifecycle begins."
        )
