"""Routers as units, and the table their endpoints are flattened into.

路由单元，以及把它们的接口拍平之后的那张表。
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, ClassVar

from canary_framework.asgi.web.binding import Endpoint
from canary_framework.asgi.web.routes import ROUTES, Route, marked
from canary_framework.core import Canary, DeclarationError, deps_of, scope_of

#: 一个路径下的接口：HTTP 方法 -> （接口，按位置排列的路径参数名）。
type _Methods = dict[str, tuple[Endpoint, tuple[str, ...]]]


class Router(Canary):
    """A unit whose marked methods are endpoints, under one prefix.

    路由单元：带标记的方法是接口，类参数是它们共同的前缀::

        class ReaderApi(Router, prefix="/readers"):
            readers = dep(ReaderService)

            @get("/{reader_id}")
            async def show(self, reader_id: int) -> Reader:
                return await self.readers.get(reader_id)

    聚合就是依赖：``dep()`` 一个路由单元，它就挂在自己之下，前缀逐层叠加::

        class Api(Router, prefix="/api"):
            readers = dep(ReaderApi)        # /api/readers/...
            loans = dep(LoanApi)            # /api/loans/...

    它仍是普通单元：有自己的依赖与钩子，接口方法是普通方法，测试里可以不经 HTTP 直接调用。
    只有被 :class:`~canary_framework.asgi.web.App` 或另一个路由单元**直接**依赖时才会被
    挂载；被两处依赖则出现在两处前缀之下。

    :param prefix: 路径前缀，以 ``/`` 开头、不以 ``/`` 结尾。子类不写时继承父类的。
    :raises DeclarationError: 前缀的形状不对。
    """

    #: 本类的前缀。
    __canary_web_prefix__: ClassVar[str] = ""

    def __init_subclass__(cls, *, prefix: str | None = None) -> None:
        super().__init_subclass__()
        if prefix is None:
            return
        if not prefix.startswith("/") or prefix.endswith("/"):
            raise DeclarationError(
                f"{cls.__name__}: prefix {prefix!r} must start with '/' and not end with one"
            )
        cls.__canary_web_prefix__ = prefix


def collect(unit: Canary, prefix: str = "") -> Iterator[tuple[str, Route, Callable[..., Any]]]:
    """Yield *unit*'s endpoints, then those of every router it depends on, recursively.

    产出 *unit* 的接口，再递归产出它直接依赖的路由单元的接口，路径已带上逐层叠加的前缀。
    必须在 *unit* 的依赖都已就位之后调用——``@init`` 满足这一点。
    """
    for bound, routes in marked(unit, ROUTES):
        for route in routes:
            yield prefix + route.path or "/", route, bound
    instances = scope_of(unit).instances
    for cls in deps_of(type(unit)):
        child = instances[cls]
        if isinstance(child, Router):
            yield from collect(child, prefix + type(child).__canary_web_prefix__)


def parse(path: str) -> tuple[tuple[str | None, ...], tuple[str, ...]]:
    """Split a path template into segments (``None`` for a parameter) and parameter names.

    把路径模板拆成段（参数段记作 ``None``）与参数名。``{name}`` 必须占一整段。

    :raises DeclarationError: 花括号没有占满一段、参数名不是标识符或重复。
    """
    segments: list[str | None] = []
    names: list[str] = []
    for segment in path.split("/")[1:]:
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            if not name.isidentifier() or name in names:
                raise DeclarationError(f"{path}: {segment} is not a usable path parameter")
            names.append(name)
            segments.append(None)
        elif "{" in segment or "}" in segment:
            raise DeclarationError(f"{path}: a path parameter takes a whole segment: {segment!r}")
        else:
            segments.append(segment)
    return tuple(segments), tuple(names)


class _Node:
    """含参数的模板组成的前缀树上的一个结点：按段往下走，静态段与参数段各有去处。"""

    __slots__ = ("literals", "methods", "param")

    def __init__(self) -> None:
        self.literals: dict[str, _Node] = {}
        self.param: _Node | None = None
        self.methods: _Methods | None = None


class Table:
    """Every endpoint of an application, looked up by path.

    一个应用的全部接口，按路径查找。不含参数的路径是一次字典查找；含参数的模板放在一棵按段
    组织的前缀树上，查找只与路径的段数有关，与接口的总数无关。每一段先试静态段、再试参数段，
    所以静态段靠左的模板优先——``/books/new`` 先于 ``/books/{book_id}``，``/a/b/{y}`` 先于
    ``/a/{x}/c``。尾斜杠严格区分。
    """

    __slots__ = ("_dynamic", "_static")

    def __init__(self) -> None:
        self._static: dict[str, _Methods] = {}
        self._dynamic = _Node()

    def add(self, path: str, route: Route, call: Callable[..., Any]) -> None:
        """Add one endpoint.

        :raises DeclarationError: 同一个方法与路径已经有接口，或方法的签名无法绑定。
        """
        segments, names = parse(path)
        endpoint = Endpoint(call, route, names)
        if names:
            node = self._dynamic
            for segment in segments:
                if segment is None:
                    node.param = node = node.param or _Node()
                else:
                    node = node.literals.setdefault(segment, _Node())
            if node.methods is None:
                node.methods = {}
            methods = node.methods
        else:
            methods = self._static.setdefault(path, {})
        if route.method in methods:
            taken = methods[route.method][0].name
            raise DeclarationError(
                f"{route.method} {path} is answered twice: by {taken} and by {endpoint.name}"
            )
        methods[route.method] = (endpoint, names)

    def find(self, path: str) -> tuple[_Methods, tuple[str, ...]] | None:
        """Return the endpoints at *path* and the values of its path parameters.

        返回 *path* 下的接口与路径参数的值；没有任何模板匹配时返回 ``None``。
        """
        methods = self._static.get(path)
        if methods is not None:
            return methods, ()
        return _walk(self._dynamic, path.split("/")[1:], 0, ())


def _walk(
    node: _Node, parts: list[str], index: int, values: tuple[str, ...]
) -> tuple[_Methods, tuple[str, ...]] | None:
    if index == len(parts):
        return None if node.methods is None else (node.methods, values)
    part = parts[index]
    child = node.literals.get(part)
    if child is not None:
        found = _walk(child, parts, index + 1, values)
        if found is not None:
            return found
    # 空段不是参数值：``/a//c`` 不匹配 ``/a/{x}/c``。
    if node.param is not None and part:
        return _walk(node.param, parts, index + 1, (*values, part))
    return None
