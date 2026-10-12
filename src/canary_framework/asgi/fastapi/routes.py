"""Route marks.

路由标记：``@get("/path")`` 只在方法上写一个标记，不改造方法，也不注册任何东西。读取标记、
把绑定方法交给 FastAPI 的是 ``router.mount``。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast, overload

#: 写在方法上的标记：该方法是哪些接口，值为 :class:`Route` 的元组。
ROUTES = "__canary_routes__"


@dataclass(frozen=True, slots=True)
class Route:
    """One mark: an HTTP method, a path, and what else FastAPI was told.

    一条标记。
    """

    method: str
    path: str
    #: 原样传给 FastAPI ``add_api_route`` 的其余参数。
    options: dict[str, Any] = field(default_factory=dict)


class _Mark(Protocol):
    def __call__[F: Callable[..., object]](self, fn: F, /) -> F: ...


class Verb:
    """An HTTP method, and the decorator that marks a unit's method as its endpoint.

    一个 HTTP 方法，同时是把单元的方法标记为接口的装饰器::

        @get("/{reader_id}")
        async def get(self, reader_id: int) -> Reader: ...

        @post(status_code=201)
        async def create(self, body: NewReader) -> Reader: ...

        @get
        async def search(self, keyword: str | None = None) -> list[Reader]: ...

    路径省略时即所在路由单元的前缀本身。其余关键字参数原样传给 FastAPI 的
    ``add_api_route``（``status_code``、``response_model``、``summary`` ……）。同一个方法
    可以带多个标记。

    :param method: HTTP 方法名，大写。
    """

    __slots__ = ("method",)

    def __init__(self, method: str) -> None:
        self.method = method

    @overload
    def __call__[F: Callable[..., object]](self, path: F, /) -> F: ...
    @overload
    def __call__(self, path: str = "", /, **options: Any) -> _Mark: ...
    def __call__(self, path: Any = "", /, **options: Any) -> Any:
        """Mark a method as an endpoint of this verb, and return it unchanged.

        给方法打上本方法的标记，原样返回。
        """
        if callable(path):
            return self._mark(path, Route(self.method, ""))
        route = Route(self.method, path, options)
        return cast("_Mark", lambda fn: self._mark(fn, route))

    @staticmethod
    def _mark[F: Callable[..., object]](fn: F, route: Route) -> F:
        setattr(fn, ROUTES, (*getattr(fn, ROUTES, ()), route))
        return fn

    def __repr__(self) -> str:
        return f"@{self.method.lower()}"


get = Verb("GET")
post = Verb("POST")
put = Verb("PUT")
patch = Verb("PATCH")
delete = Verb("DELETE")


def routes_of(unit: object) -> list[tuple[Route, Callable[..., object]]]:
    """Return *unit*'s marked methods, bound, with their marks — base classes first.

    返回 *unit* 上带标记的绑定方法及其标记，基类在前，同一个类内按定义顺序。

    与生命周期钩子一样按**属性名**解析：子类覆盖同名方法即替换；覆盖但不再标记时，它不再
    是接口。
    """
    names: dict[str, None] = {}
    for klass in reversed(type(unit).__mro__):
        for name, value in vars(klass).items():
            if hasattr(value, ROUTES):
                names[name] = None
    found: list[tuple[Route, Callable[..., object]]] = []
    for name in names:
        bound = getattr(unit, name)
        found.extend((route, bound) for route in getattr(bound, ROUTES, ()))
    return found
