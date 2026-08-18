"""Integration tests — Canary + ``@web_cocoa`` driven through Starlette's TestClient."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel
from starlette.requests import Request
from starlette.testclient import TestClient

from canary_framework import Canary, cocoa, on_start, on_stop
from canary_framework.web import Header, Query, RouteRegistrationError, get, post, web_cocoa

pytestmark = pytest.mark.integration


class BorrowRequest(BaseModel):
    member_id: int


class BorrowResult(BaseModel):
    book_id: int
    member_id: int


def test_path_param_and_cocoa_dep() -> None:
    @cocoa
    class Repo:
        def get(self, book_id: int) -> dict:
            return {"id": book_id, "title": "三体"}

    @web_cocoa(deps=[Repo])
    class API:
        @get("/books/{book_id}")
        async def get_book(self, book_id: int) -> dict:
            return self.repo.get(book_id)

    with TestClient(Canary(API)) as client:
        r = client.get("/books/42")

    assert r.status_code == 200
    assert r.json() == {"id": 42, "title": "三体"}  # 路径参数已按注解转型为 int


def test_same_named_mixin_routes_are_all_served() -> None:
    class KbMixin:
        @get("/kb/create")
        async def create(self) -> dict:
            return {"kind": "kb"}

    class FileMixin:
        @get("/file/create")
        async def create(self) -> dict:
            return {"kind": "file"}

    class CollMixin:
        @get("/coll/create")
        async def create(self) -> dict:
            return {"kind": "coll"}

    @web_cocoa
    class API(KbMixin, FileMixin, CollMixin):
        pass

    with TestClient(Canary(API)) as client:
        assert client.get("/kb/create").json() == {"kind": "kb"}
        assert client.get("/file/create").json() == {"kind": "file"}
        assert client.get("/coll/create").json() == {"kind": "coll"}


def test_query_param_default_and_coercion() -> None:
    @web_cocoa
    class API:
        @get("/search")
        async def search(self, q: str = "", limit: int = 5) -> list[str]:
            return [q] * limit

    with TestClient(Canary(API)) as client:
        r = client.get("/search", params={"q": "x", "limit": "2"})

    assert r.status_code == 200
    assert r.json() == ["x", "x"]


def test_missing_required_query_is_422() -> None:
    @web_cocoa
    class API:
        @get("/need")
        async def need(self, q: str) -> dict:
            return {"q": q}

    with TestClient(Canary(API)) as client:
        r = client.get("/need")

    assert r.status_code == 422


def test_pydantic_body_and_response() -> None:
    @web_cocoa
    class API:
        @post("/borrow/{book_id}")
        async def borrow(self, book_id: int, body: BorrowRequest) -> BorrowResult:
            return BorrowResult(book_id=book_id, member_id=body.member_id)

    with TestClient(Canary(API)) as client:
        r = client.post("/borrow/7", json={"member_id": 3})

    assert r.status_code == 200
    assert r.json() == {"book_id": 7, "member_id": 3}


def test_body_validation_failure_is_422() -> None:
    @web_cocoa
    class API:
        @post("/borrow/{book_id}")
        async def borrow(self, book_id: int, body: BorrowRequest) -> dict:
            return {"book_id": book_id}

    with TestClient(Canary(API)) as client:
        r = client.post("/borrow/7", json={"member_id": "not-an-int"})

    assert r.status_code == 422


def test_header_injection_underscore_to_hyphen() -> None:
    @web_cocoa
    class API:
        @get("/whoami")
        async def whoami(self, x_token: str = Header(default="")) -> dict:
            return {"token": x_token}

    with TestClient(Canary(API)) as client:
        r = client.get("/whoami", headers={"x-token": "secret"})

    assert r.json() == {"token": "secret"}


def test_request_injection() -> None:
    @web_cocoa
    class API:
        @get("/echo")
        async def echo(self, request: Request) -> dict:
            return {"path": request.url.path, "method": request.method}

    with TestClient(Canary(API)) as client:
        r = client.get("/echo")

    assert r.json() == {"path": "/echo", "method": "GET"}


def test_annotated_query_under_future_annotations() -> None:
    @web_cocoa
    class API:
        @get("/items")
        async def items(self, limit: Annotated[int, Query(default=3)]) -> list[int]:
            return [1] * limit

    with TestClient(Canary(API)) as client:
        assert client.get("/items").json() == [1, 1, 1]
        assert client.get("/items", params={"limit": "1"}).json() == [1]


def test_openapi_document() -> None:
    @web_cocoa
    class API:
        @get("/books/{book_id}")
        async def get_book(self, book_id: int) -> dict:
            return {}

    with TestClient(Canary(API)) as client:
        r = client.get("/openapi.json")

    assert r.status_code == 200
    doc = r.json()
    assert doc["openapi"] == "3.1.0"
    assert "/books/{book_id}" in doc["paths"]


def test_docs_pages_served() -> None:
    @web_cocoa
    class API:
        @get("/x")
        async def x(self) -> dict:
            return {}

    with TestClient(Canary(API)) as client:
        assert "SwaggerUIBundle" in client.get("/docs").text
        assert "redoc" in client.get("/redoc").text


def test_lifespan_drives_start_and_stop() -> None:
    events: list[str] = []

    @web_cocoa
    class API:
        @on_start
        def up(self) -> None:
            events.append("up")

        @on_stop
        def down(self) -> None:
            events.append("down")

        @get("/")
        async def root(self) -> dict:
            return {"ok": True}

    with TestClient(Canary(API)) as client:
        assert client.get("/").json() == {"ok": True}
        assert "up" in events

    assert "down" in events


async def test_duplicate_route_raises() -> None:
    @web_cocoa
    class API:
        @get("/x")
        async def a(self) -> None: ...

        @get("/x")
        async def b(self) -> None: ...

    app = Canary(API)
    with pytest.raises(RouteRegistrationError):
        await app.init()
        await app.start()
