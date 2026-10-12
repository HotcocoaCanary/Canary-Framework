"""Route marks and error marks.

路由标记与异常标记：只在方法上写一个标记，不改造方法，也不注册任何东西。读取标记的是
``router`` 与 ``app``。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, overload

from canary_framework.core import DeclarationError

#: 写在方法上的标记：该方法是哪些接口，值为 :class:`Route` 的元组。
ROUTES = "__canary_web_routes__"
#: 写在方法上的标记：该方法处理哪些异常类型，值为类型的元组。
ERRORS = "__canary_web_errors__"


@dataclass(frozen=True, slots=True)
class Route:
    """One mark: an HTTP method, a path, and the status of a successful answer.

    一条标记。
    """

    method: str
    path: str
    status: int = 200


class Verb:
    """An HTTP method, and the decorator that marks a unit's method as its endpoint.

    一个 HTTP 方法，同时是把单元的方法标记为接口的装饰器::

        @get("/{reader_id}")
        async def show(self, reader_id: int) -> Reader: ...

        @post(status=201)
        async def create(self, body: NewReader) -> Reader: ...

        @get
        async def search(self, keyword: str | None = None) -> list[Reader]: ...

    路径省略时即所在路由单元的前缀本身。同一个方法可以带多个标记。

    :param method: HTTP 方法名，大写。
    """

    __slots__ = ("method",)

    def __init__(self, method: str) -> None:
        self.method = method

    @overload
    def __call__[F: Callable[..., object]](self, path: F, /) -> F: ...
    @overload
    def __call__[F: Callable[..., object]](
        self, path: str = "", /, *, status: int = 200
    ) -> Callable[[F], F]: ...
    def __call__(self, path: Any = "", /, *, status: int = 200) -> Any:
        """Mark a method as an endpoint of this verb, and return it unchanged.

        给方法打上本方法的标记，原样返回。

        :param path: 相对所在单元前缀的路径，``""`` 或以 ``/`` 开头。``{name}`` 占一整段，
            是路径参数。
        :param status: 成功时的状态码。
        :raises DeclarationError: 路径不为空又不以 ``/`` 开头。
        """
        if callable(path):
            return _mark(path, ROUTES, Route(self.method, ""))
        if path and not path.startswith("/"):
            raise DeclarationError(
                f"@{self.method.lower()}({path!r}): a path is empty or starts with '/'"
            )
        route = Route(self.method, path, status)
        return lambda fn: _mark(fn, ROUTES, route)

    def __repr__(self) -> str:
        return f"@{self.method.lower()}"


get = Verb("GET")
post = Verb("POST")
put = Verb("PUT")
patch = Verb("PATCH")
delete = Verb("DELETE")


def error[F: Callable[..., object]](*types: type[Exception]) -> Callable[[F], F]:
    """Mark an application's method as the handler of these exception types.

    把应用单元的方法标记为这些异常类型的处理器::

        class LibraryApi(App):
            @error(DomainError)
            async def on_domain_error(self, request: Request, exc: DomainError) -> Response:
                return Response.json({"msg": exc.message}, status=exc.code)

    接口抛出的异常交给类型最贴近的那个处理器（按异常类型的继承顺序找），返回值与接口的
    返回值同样处理；和接口一样，普通 ``def`` 的处理器在线程池里运行。没有处理器的异常应答 500。

    :param types: 要处理的异常类型，至少一个。
    :raises DeclarationError: 没有给出类型。
    """
    if not types:
        raise DeclarationError("@error(): name at least one exception type")
    return lambda fn: _mark(fn, ERRORS, *types)


def _mark[F: Callable[..., object]](fn: F, attr: str, *values: object) -> F:
    setattr(fn, attr, (*getattr(fn, attr, ()), *values))
    return fn


def marked(unit: object, attr: str) -> list[tuple[Callable[..., Any], tuple[Any, ...]]]:
    """Return *unit*'s methods carrying *attr*, bound, with the marks — base classes first.

    返回 *unit* 上带某种标记的绑定方法及其标记，基类在前，同一个类内按定义顺序。

    与生命周期钩子一样按**属性名**解析：子类覆盖同名方法即替换；覆盖但不再标记时，它不再
    带有这个标记。
    """
    names: dict[str, None] = {}
    for klass in reversed(type(unit).__mro__):
        for name, value in vars(klass).items():
            if hasattr(value, attr):
                names[name] = None
    found = []
    for name in names:
        bound = getattr(unit, name)
        marks = getattr(bound, attr, ())
        if marks:
            found.append((bound, marks))
    return found
