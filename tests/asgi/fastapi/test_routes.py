"""路由标记：FastAPI 自己的装饰器，被记下来，按属性名解析。"""

from __future__ import annotations

import inspect

import pytest
from fastapi import APIRouter

from canary_framework import Canary
from canary_framework.asgi import fastapi as marks
from canary_framework.asgi.fastapi import api_route, get, patch, post, put, websocket
from canary_framework.asgi.fastapi.routes import ROUTES, Route, routes_of

pytestmark = pytest.mark.unit

VERBS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")


def _marks(unit: object) -> list[tuple[str, str, str]]:
    return [(route.verb, route.args[0], bound.__name__) for route, bound in routes_of(unit)]


def test_a_mark_returns_the_function_unchanged() -> None:
    async def handler(self: object) -> None: ...

    assert get("/x")(handler) is handler
    assert getattr(handler, ROUTES) == (Route("get", ("/x",)),)


def test_the_arguments_are_recorded_as_they_were_written() -> None:
    @post("", status_code=201, summary="新建")
    async def create(self: object) -> None: ...

    assert getattr(create, ROUTES) == (
        Route("post", ("",), {"status_code": 201, "summary": "新建"}),
    )


def test_one_method_can_carry_several_marks() -> None:
    @put("/a")
    @patch("/a")
    async def update(self: object) -> None: ...

    assert [(r.verb, r.args) for r in getattr(update, ROUTES)] == [
        ("patch", ("/a",)),
        ("put", ("/a",)),
    ]


@pytest.mark.parametrize("name", [*VERBS, "api_route", "websocket"])
def test_each_mark_has_the_name_and_signature_of_the_native_decorator(name: str) -> None:
    mark = getattr(marks, name)
    native = inspect.signature(getattr(APIRouter, name))
    assert mark.__name__ == name
    assert list(inspect.signature(mark).parameters) == list(native.parameters)[1:]


def test_a_mark_without_a_path_is_refused_as_fastapi_would() -> None:
    async def handler(self: object) -> None: ...

    with pytest.raises(TypeError, match=r"@get takes a path, as FastAPI's does: @get\('/'\)"):
        get(handler)  # type: ignore[arg-type]


def test_routes_are_read_base_first_in_definition_order() -> None:
    class Base(Canary):
        @get("/health")
        async def health(self) -> None: ...

    class Api(Base):
        @get("")
        async def search(self) -> None: ...

        @api_route("/{item_id}", methods=["GET", "HEAD"])
        async def show(self, item_id: int) -> None: ...

        @websocket("/events")
        async def events(self) -> None: ...

    assert _marks(Api()) == [
        ("get", "/health", "health"),
        ("get", "", "search"),
        ("api_route", "/{item_id}", "show"),
        ("websocket", "/events", "events"),
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

    assert _marks(Child()) == [("post", "/a2", "a")]


def test_the_endpoints_are_bound_methods() -> None:
    class Api(Canary):
        @get("/")
        async def who(self) -> Api:
            return self

    api = Api()
    [(_, bound)] = routes_of(api)
    assert bound.__self__ is api  # type: ignore[attr-defined]
