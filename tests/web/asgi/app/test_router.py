"""路由表：拍平、匹配与优先级。"""

from __future__ import annotations

import pytest

from canary_framework import DeclarationError, dep
from canary_framework.test import running
from canary_framework.web.asgi.app import App, Router, get, post
from canary_framework.web.asgi.app.router import Table, collect, parse
from canary_framework.web.asgi.app.routes import ROUTES, Route, marked

pytestmark = pytest.mark.unit


def test_a_mark_returns_the_function_unchanged_and_marks_stack() -> None:
    async def handler(self: object) -> None: ...

    assert get(handler) is handler
    assert post("/x", status=201)(handler) is handler
    assert getattr(handler, ROUTES) == (Route("GET", ""), Route("POST", "/x", 201))
    assert repr(get) == "@get"


def test_marks_are_resolved_by_attribute_name() -> None:
    class Base(Router):
        @get("/a")
        async def a(self) -> None: ...

        @get("/b")
        async def b(self) -> None: ...

    class Child(Base):
        @get("/a2")
        async def a(self) -> None: ...

        async def b(self) -> None: ...  # 覆盖但不再标记：不再是接口

    found = [(bound.__name__, marks) for bound, marks in marked(Child(), ROUTES)]
    assert found == [("a", (Route("GET", "/a2"),))]


def test_a_template_is_split_into_segments_and_names() -> None:
    assert parse("/") == (("",), ())
    assert parse("/a/{x}/b/{y}") == (("a", None, "b", None), ("x", "y"))
    for bad in ("/a/{x}.json", "/a/{x}/{x}", "/a/{1x}", "/a/{}"):
        with pytest.raises(DeclarationError):
            parse(bad)


def test_the_leftmost_static_segment_wins() -> None:
    async def first(y: str) -> None: ...
    async def second(x: str) -> None: ...
    async def both(x: str, y: str) -> None: ...

    table = Table()
    table.add("/a/{x}/{y}", Route("GET", ""), both)
    table.add("/a/{x}/c", Route("GET", ""), second)
    table.add("/a/b/{y}", Route("GET", ""), first)

    def answered_by(path: str) -> tuple[str, tuple[str, ...]]:
        found = table.find(path)
        assert found is not None
        methods, values = found
        return methods["GET"][0].name.rsplit(".", 1)[-1], values

    assert answered_by("/a/b/c") == ("first", ("c",))
    assert answered_by("/a/z/c") == ("second", ("z",))
    assert answered_by("/a/z/z") == ("both", ("z", "z"))
    assert table.find("/a/b") is None
    assert table.find("/a//c") is None, "空段不是参数值"


async def test_a_router_depended_on_twice_appears_under_both_prefixes() -> None:
    class Shared(Router, prefix="/shared"):
        @get("/ping")
        async def ping(self) -> None: ...

    class Left(Router, prefix="/left"):
        shared = dep(Shared)

    class Right(Router, prefix="/right"):
        shared = dep(Shared)

    class Root(App):
        left = dep(Left)
        right = dep(Right)

    class Inherits(Shared): ...

    async with running(Root) as root:
        assert [path for path, _, _ in collect(root)] == [
            "/left/shared/ping",
            "/right/shared/ping",
        ]
    assert Inherits.__canary_web_prefix__ == "/shared"
