"""Integration — everything a request can get wrong, and what the caller sees.

请求可能出错的所有形状，以及调用方看到什么。判据只有一条：**调用方发错了是 4xx，
服务端写错了是 5xx**，两者不能混。
"""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from canary_framework import Canary, DeclarationError, cocoa
from canary_framework.web import RouteRegistrationError, delete, get, post, web_cocoa

pytestmark = pytest.mark.integration


class Item(BaseModel):
    name: str


class Book(BaseModel):
    title: str
    stock: int


class Half(BaseModel):
    a: int


class Other(BaseModel):
    b: int


@web_cocoa
class Api:
    @post("/items")
    async def create(self, item: Item) -> dict:
        return {"name": item.name}

    @post("/optional")
    async def optional(self, item: Item | None = None) -> dict:
        return {"got": item is not None}


def test_every_bad_body_is_a_422_not_a_500() -> None:
    """从前全是 500 —— request.json() 抛的 JSONDecodeError 没有被接住。"""
    with TestClient(Canary(Api), raise_server_exceptions=False) as client:
        assert client.post("/items").status_code == 422  # 空 body
        assert client.post("/items", content=b"{oops").status_code == 422  # 语法错
        assert client.post("/items", data={"name": "x"}).status_code == 422  # 发成表单
        assert client.post("/items", json={"wrong": 1}).status_code == 422  # 字段不对


def test_an_optional_body_can_actually_be_omitted() -> None:
    """有缺省值的请求体形参，不传 body 就该用缺省值——从前直接 500。"""
    with TestClient(Canary(Api), raise_server_exceptions=False) as client:
        assert client.post("/optional").json() == {"got": False}
        assert client.post("/optional", json={"name": "x"}).json() == {"got": True}


async def test_two_body_parameters_are_refused_at_assembly() -> None:
    """从前两个形参各拿到整份 body，谁也没提醒。"""

    @web_cocoa
    class Bad:
        @post("/two")
        async def two(self, x: Half, y: Other) -> dict:
            return {}

    canary = Canary(Bad)
    await canary.init()
    with pytest.raises(RouteRegistrationError, match="request-body parameters"):
        await canary.start()


def test_annotated_constraints_are_enforced_and_documented() -> None:
    """从前只取 Annotated 的第一项，Field(gt=0) 这类约束被无声丢掉。"""

    @web_cocoa
    class Constrained:
        @get("/items")
        async def items(self, page: Annotated[int, Field(gt=0, le=100)] = 1) -> dict:
            return {"page": page}

    with TestClient(Canary(Constrained), raise_server_exceptions=False) as client:
        assert client.get("/items", params={"page": "-5"}).status_code == 422
        assert client.get("/items", params={"page": "999"}).status_code == 422
        assert client.get("/items", params={"page": "7"}).json() == {"page": 7}

        schema = client.get("/openapi.json").json()["paths"]["/items"]["get"]["parameters"][0]
        assert schema["schema"]["exclusiveMinimum"] == 0  # 约束也要进文档


def test_a_handler_breaking_its_own_return_type_is_a_500() -> None:
    """返回值不符合声明是**服务端**的 bug，不能伪装成客户端的错，也不能悄悄发出去。"""

    @web_cocoa
    class Lying:
        @get("/book")
        async def book(self) -> Book:
            return {"title": "三体"}  # type: ignore[return-value]

    with TestClient(Canary(Lying), raise_server_exceptions=False) as client:
        assert client.get("/book").status_code == 500


async def test_routes_on_a_plain_cocoa_are_refused() -> None:
    """从前：装饰器打上了、不报错、路由也不见了。"""

    @cocoa
    class Ghost:
        @get("/ghost")
        async def ghost(self) -> dict:
            return {}

    @web_cocoa(deps=[Ghost])
    class Host:
        @get("/real")
        async def real(self) -> dict:
            return {}

    with pytest.raises(DeclarationError, match="plain @cocoa"):
        await Canary(Host).init()


def test_a_prefix_without_a_slash_is_normalised() -> None:
    """@get("ping") 早就会自动补斜杠，prefix 却会一路拼成 "api/ping" 再炸出 AssertionError。"""

    @web_cocoa(prefix="api/v1/")
    class Api2:
        @get("ping")
        async def ping(self) -> dict:
            return {"ok": True}

    with TestClient(Canary(Api2)) as client:
        assert client.get("/api/v1/ping").json() == {"ok": True}


def test_status_code_and_doc_metadata() -> None:
    """新建资源该是 201、删除该是 204 —— 从前只能自己造 Response，那样就丢了返回类型和文档。"""

    @web_cocoa(prefix="/api", tags=["library"])
    class Meta:
        @post("/books", status_code=201, tags=["write"], summary="新建一本书")
        async def create(self) -> dict:
            """更长的说明直接写 docstring，不必抄进装饰器参数。"""
            return {"id": 1}

        @delete("/books/{book_id}", status_code=204)
        async def remove(self, book_id: int) -> None:
            return None

        @get("/legacy", deprecated=True)
        async def legacy(self) -> dict:
            return {}

    with TestClient(Canary(Meta)) as client:
        created = client.post("/api/books")
        assert created.status_code == 201
        assert created.json() == {"id": 1}

        removed = client.delete("/api/books/1")
        assert removed.status_code == 204
        assert removed.content == b""  # 204 不能带响应体

        doc = client.get("/openapi.json").json()["paths"]
        create_op = doc["/api/books"]["post"]
        assert "201" in create_op["responses"]
        assert create_op["summary"] == "新建一本书"
        assert create_op["description"].startswith("更长的说明")
        assert create_op["tags"] == ["library", "write"]  # 单元级在前，路由级在后
        assert doc["/api/books/{book_id}"]["delete"]["responses"]["204"] == {
            "description": "Successful Response"
        }
        assert doc["/api/legacy"]["get"]["deprecated"] is True


def test_a_handler_building_its_own_response_keeps_its_own_status() -> None:
    """按情况变化的状态码仍然归 handler —— 声明的 status_code 只管"没自己造响应"那条路。"""

    @web_cocoa
    class Own:
        @get("/x", status_code=201)
        async def x(self) -> Response:
            return JSONResponse({"ok": True}, status_code=202)

    with TestClient(Canary(Own)) as client:
        assert client.get("/x").status_code == 202
