"""接口表：应用单元拍平之后的全部接口，以及只靠它生成一份 OpenAPI 文档。"""

from __future__ import annotations

import inspect
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, TypeAdapter

from canary_framework import dep, init
from canary_framework.web.asgi.app import (
    App,
    Endpoint,
    Request,
    Response,
    Router,
    delete,
    get,
    post,
)

pytestmark = pytest.mark.functional


class Reader(BaseModel):
    id: int
    name: str


class NewReader(BaseModel):
    name: str


class ReaderApi(Router, prefix="/readers"):
    @get
    async def search(self, keyword: str | None = None, tag: list[str] = []) -> list[Reader]:  # noqa: B006
        """按关键字找读者。

        第二段不进摘要。
        """
        return []

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return Reader(id=reader_id, name="七")

    @post(status=201)
    async def create(self, body: NewReader) -> Reader:
        return Reader(id=1, name=body.name)

    @delete("/{reader_id}")
    async def remove(self, reader_id: int) -> None:
        return None


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)

    @post("/echo")
    async def echo(self, request: Request, body: bytes = b"") -> Response:
        return Response(body)


def openapi(endpoints: tuple[Endpoint, ...], title: str, version: str = "0.1.0") -> dict[str, Any]:
    """只读接口表，生成 OpenAPI 3.1 文档——与文档页上的写法相同。"""
    schemas: dict[str, Any] = {}

    def schema(annotation: Any, mode: Any = "validation") -> dict[str, Any]:
        found = TypeAdapter(annotation).json_schema(
            ref_template="#/components/schemas/{model}", mode=mode
        )
        schemas.update(found.pop("$defs", {}))
        return found

    paths: dict[str, Any] = {}
    for endpoint in endpoints:
        operation: dict[str, Any] = {"operationId": endpoint.name}
        if endpoint.call.__doc__:
            operation["summary"] = inspect.cleandoc(endpoint.call.__doc__).splitlines()[0]
        operation["parameters"] = [
            {"name": p.name, "in": p.source, "required": p.required, "schema": schema(p.annotation)}
            for p in endpoint.params
            if p.source in ("path", "query")
        ]
        for p in endpoint.params:
            if p.source == "body" and p.annotation is not bytes:
                content = {"application/json": {"schema": schema(p.annotation)}}
                operation["requestBody"] = {"required": p.required, "content": content}
        if endpoint.returns is type(None):
            status = 204 if endpoint.status == 200 else endpoint.status
            operation["responses"] = {str(status): {"description": "No Content"}}
        elif endpoint.returns in (Any, Response):
            operation["responses"] = {str(endpoint.status): {"description": "OK"}}
        else:
            content = {"application/json": {"schema": schema(endpoint.returns, "serialization")}}
            operation["responses"] = {
                str(endpoint.status): {"description": "OK", "content": content}
            }
        paths.setdefault(endpoint.path, {})[endpoint.method.lower()] = operation
    return {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version},
        "paths": paths,
        "components": {"schemas": schemas},
    }


class Library(App):
    api = dep(Api)

    @init
    def describe(self) -> None:
        self.document = openapi(self.endpoints, "Library")

    @get("/openapi.json")
    async def spec(self) -> dict[str, Any]:
        return self.document


# ---------------------------------------------------------------- the table


async def test_endpoints_are_the_flattened_table_own_first_then_by_declaration() -> None:
    async with Library() as app:
        assert [(e.method, e.path) for e in app.endpoints] == [
            ("GET", "/openapi.json"),
            ("POST", "/api/echo"),
            ("GET", "/api/readers"),
            ("GET", "/api/readers/{reader_id}"),
            ("POST", "/api/readers"),
            ("DELETE", "/api/readers/{reader_id}"),
        ]
        assert isinstance(app.endpoints, tuple)


async def test_an_endpoint_describes_its_method() -> None:
    async with Library() as app:
        create = next(e for e in app.endpoints if e.name == "ReaderApi.create")
        assert (create.method, create.path, create.status) == ("POST", "/api/readers", 201)
        assert create.returns is Reader
        assert getattr(create.call, "__self__", None) is app.api.readers
        assert repr(create) == "<Endpoint POST /api/readers -> ReaderApi.create>"

        remove = next(e for e in app.endpoints if e.name == "ReaderApi.remove")
        assert remove.returns is type(None)

        echo = next(e for e in app.endpoints if e.name == "Api.echo")
        assert echo.returns is Response


async def test_params_say_where_each_value_comes_from() -> None:
    async with Library() as app:
        by_name = {e.name: e for e in app.endpoints}

        described = [
            (p.name, p.source, p.annotation, p.required) for p in by_name["ReaderApi.search"].params
        ]
        assert described == [
            ("keyword", "query", str | None, False),
            ("tag", "query", list[str], False),
        ]
        assert by_name["ReaderApi.search"].params[0].default is None

        (reader_id,) = by_name["ReaderApi.show"].params
        assert (reader_id.name, reader_id.source, reader_id.annotation) == (
            "reader_id",
            "path",
            int,
        )
        assert reader_id.required
        assert reader_id.default is inspect.Parameter.empty
        assert repr(reader_id) == "<Param reader_id from path>"

        (body,) = by_name["ReaderApi.create"].params
        assert (body.source, body.annotation, body.required) == ("body", NewReader, True)

        request, raw = by_name["Api.echo"].params
        assert (request.source, request.annotation) == ("request", Request)
        assert (raw.source, raw.annotation, raw.default) == ("body", bytes, b"")


async def test_a_router_mounted_twice_is_listed_under_both_prefixes() -> None:
    class Twice(App):
        api = dep(Api)
        readers = dep(ReaderApi)

    async with Twice() as app:
        paths = [e.path for e in app.endpoints if e.name == "ReaderApi.show"]
        assert paths == ["/api/readers/{reader_id}", "/readers/{reader_id}"]


def test_endpoints_are_not_there_before_init() -> None:
    with pytest.raises(AttributeError):
        _ = Library().endpoints


# ---------------------------------------------------------------- OpenAPI from the table


async def test_the_table_is_enough_to_write_openapi() -> None:
    async with (
        Library() as app,
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        document = (await client.get("/openapi.json")).json()

    assert document["openapi"] == "3.1.0"
    assert set(document["components"]["schemas"]) == {"Reader"}
    assert set(document["paths"]) == {
        "/openapi.json",
        "/api/echo",
        "/api/readers",
        "/api/readers/{reader_id}",
    }

    search = document["paths"]["/api/readers"]["get"]
    assert search["summary"] == "按关键字找读者。"
    assert search["parameters"] == [
        {
            "name": "keyword",
            "in": "query",
            "required": False,
            "schema": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        {
            "name": "tag",
            "in": "query",
            "required": False,
            "schema": {"type": "array", "items": {"type": "string"}},
        },
    ]
    assert search["responses"]["200"]["content"]["application/json"]["schema"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/Reader"},
    }

    create = document["paths"]["/api/readers"]["post"]
    body = create["requestBody"]
    assert body["required"] is True
    assert body["content"]["application/json"]["schema"]["properties"] == {
        "name": {"title": "Name", "type": "string"}
    }
    assert list(create["responses"]) == ["201"]

    show = document["paths"]["/api/readers/{reader_id}"]["get"]
    assert show["parameters"] == [
        {"name": "reader_id", "in": "path", "required": True, "schema": {"type": "integer"}}
    ]
    remove = document["paths"]["/api/readers/{reader_id}"]["delete"]
    assert remove["responses"] == {"204": {"description": "No Content"}}
    assert "requestBody" not in document["paths"]["/api/echo"]["post"]
