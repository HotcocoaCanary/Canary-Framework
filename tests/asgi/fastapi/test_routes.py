"""路由标记：只打标记，按属性名解析。"""

from __future__ import annotations

import pytest

from canary_framework import Canary
from canary_framework.asgi.fastapi import delete, get, patch, post, put
from canary_framework.asgi.fastapi.routes import ROUTES, Route, routes_of

pytestmark = pytest.mark.unit


def _marks(unit: object) -> list[tuple[str, str, str]]:
    return [(route.method, route.path, bound.__name__) for route, bound in routes_of(unit)]


def test_a_mark_returns_the_function_unchanged() -> None:
    async def handler(self: object) -> None: ...

    assert get("/x")(handler) is handler
    assert getattr(handler, ROUTES) == (Route("GET", "/x"),)


def test_a_bare_verb_marks_the_prefix_itself() -> None:
    @post
    async def create(self: object) -> None: ...

    assert getattr(create, ROUTES) == (Route("POST", ""),)


def test_options_travel_with_the_mark() -> None:
    @post(status_code=201, summary="新建")
    async def create(self: object) -> None: ...

    assert getattr(create, ROUTES) == (Route("POST", "", {"status_code": 201, "summary": "新建"}),)


def test_one_method_can_carry_several_marks() -> None:
    @put("/a")
    @patch("/a")
    async def update(self: object) -> None: ...

    assert [(r.method, r.path) for r in getattr(update, ROUTES)] == [("PATCH", "/a"), ("PUT", "/a")]


def test_each_verb_names_its_method() -> None:
    assert [verb.method for verb in (get, post, put, patch, delete)] == [
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ]
    assert repr(delete) == "@delete"


def test_routes_are_read_base_first_in_definition_order() -> None:
    class Base(Canary):
        @get("/health")
        async def health(self) -> None: ...

    class Api(Base):
        @get
        async def search(self) -> None: ...

        @get("/{item_id}")
        async def get(self, item_id: int) -> None: ...

    assert _marks(Api()) == [
        ("GET", "/health", "health"),
        ("GET", "", "search"),
        ("GET", "/{item_id}", "get"),
    ]


def test_an_override_replaces_and_an_unmarked_override_removes() -> None:
    class Base(Canary):
        @get("/a")
        async def a(self) -> None: ...

        @get("/b")
        async def b(self) -> None: ...

    class Child(Base):
        @post("/a2")
        async def a(self) -> None: ...

        async def b(self) -> None: ...

    assert _marks(Child()) == [("POST", "/a2", "a")]


def test_the_endpoints_are_bound_methods() -> None:
    class Api(Canary):
        @get
        async def who(self) -> Api:
            return self

    api = Api()
    [(_, bound)] = routes_of(api)
    assert bound.__self__ is api  # type: ignore[attr-defined]
