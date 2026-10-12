"""路由单元：聚合就是依赖，前缀逐层叠加。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from canary_framework import Canary, dep, init, scope_of
from canary_framework.asgi.fastapi import Router, delete, get, mount, post
from canary_framework.test import unit

pytestmark = pytest.mark.integration


class Reader(BaseModel):
    name: str


class ReaderService(Canary):
    async def find(self, reader_id: int) -> Reader:
        return Reader(name=f"reader-{reader_id}")


class ReaderApi(Router, prefix="/readers", tags=["读者"]):
    readers = dep(ReaderService)
    routes = "属性叫什么都不与 FastAPI 冲突"

    @get
    async def search(self, keyword: str | None = None) -> list[Reader]:
        return [Reader(name=keyword or "all")]

    @get("/{reader_id}")
    async def get(self, reader_id: int) -> Reader:
        return await self.readers.find(reader_id)

    @post(status_code=201)
    async def create(self, body: Reader) -> Reader:
        return body

    @delete("/{reader_id}", status_code=204)
    async def delete(self, reader_id: int) -> None: ...


class LoanApi(Router, prefix="/loans", tags=["借阅"]):
    @get
    async def all(self) -> list[str]:
        return []


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)
    loans = dep(LoanApi)


class App(Canary):
    """最小的宿主：在 @init 里把图挂到一个 FastAPI 应用上，不监听端口。"""

    api = dep(Api)

    @init
    def assemble(self) -> None:
        self.app = FastAPI()
        mount(self, self.app)


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _json(app: FastAPI, method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async with _client(app) as client:
        response = await client.request(method, path, **kwargs)
        return response.status_code, response.json() if response.content else None


async def test_prefixes_add_up_along_the_dependency_graph() -> None:
    async with App() as root:
        spec = root.app.openapi()["paths"]
        assert sorted(spec) == ["/api/loans", "/api/readers", "/api/readers/{reader_id}"]


async def test_fastapi_parses_validates_and_serialises() -> None:
    async with App() as root:
        app = root.app
        assert await _json(app, "GET", "/api/readers", params={"keyword": "x"}) == (
            200,
            [{"name": "x"}],
        )
        assert await _json(app, "GET", "/api/readers/7") == (200, {"name": "reader-7"})
        assert await _json(app, "POST", "/api/readers", json={"name": "张三"}) == (
            201,
            {"name": "张三"},
        )
        assert await _json(app, "DELETE", "/api/readers/7") == (204, None)
        assert (await _json(app, "GET", "/api/readers/seven"))[0] == 422
        assert (await _json(app, "POST", "/api/readers", json={}))[0] == 422


async def test_tags_reach_the_openapi_document() -> None:
    async with App() as root:
        paths = root.app.openapi()["paths"]
        assert paths["/api/readers"]["get"]["tags"] == ["读者"]
        assert paths["/api/loans"]["get"]["tags"] == ["借阅"]


async def test_a_router_is_still_a_plain_unit() -> None:
    async with App() as root:
        api = unit(root, ReaderApi)
        assert await api.get(3) == Reader(name="reader-3")
        assert api.routes == "属性叫什么都不与 FastAPI 冲突"


async def test_a_double_is_mounted_in_place_of_the_router() -> None:
    class FakeReaderApi(ReaderApi):
        @get("/{reader_id}")
        async def get(self, reader_id: int) -> Reader:
            return Reader(name="fake")

    root = App()
    scope_of(root).provide(ReaderApi, FakeReaderApi())
    async with root:
        assert await _json(root.app, "GET", "/api/readers/7") == (200, {"name": "fake"})


async def test_a_subclass_inherits_the_class_parameters_it_does_not_override() -> None:
    class Renamed(ReaderApi, prefix="/members"): ...

    class Same(ReaderApi): ...

    assert Renamed.__canary_router__ == {"prefix": "/members", "tags": ["读者"]}
    assert Same.__canary_router__ == ReaderApi.__canary_router__
    assert Router.__canary_router__ == {}


async def test_other_parameters_go_to_the_api_router() -> None:
    class Old(Router, prefix="/old", deprecated=True):
        @get
        async def index(self) -> str:
            return "old"

    class Host(Canary):
        old = dep(Old)

        @init
        def assemble(self) -> None:
            self.app = FastAPI()
            mount(self, self.app)

    async with Host() as root:
        assert root.app.openapi()["paths"]["/old"]["get"]["deprecated"] is True


async def test_only_routers_depended_on_directly_are_mounted() -> None:
    class Hidden(Router, prefix="/hidden"):
        @get
        async def index(self) -> str:
            return "hidden"

    class Service(Canary):
        hidden = dep(Hidden)

    class Host(Canary):
        service = dep(Service)

        @init
        def assemble(self) -> None:
            self.app = FastAPI()
            mount(self, self.app)

    async with Host() as root:
        assert root.app.openapi()["paths"] == {}


async def test_a_router_depended_on_twice_appears_under_both_prefixes() -> None:
    class Shared(Router, prefix="/shared"):
        @get
        async def index(self) -> str:
            return "shared"

    class V1(Router, prefix="/v1"):
        shared = dep(Shared)

    class V2(Router, prefix="/v2"):
        shared = dep(Shared)

    class Host(Canary):
        v1 = dep(V1)
        v2 = dep(V2)

        @init
        def assemble(self) -> None:
            self.app = FastAPI()
            mount(self, self.app)

    async with Host() as root:
        assert sorted(root.app.openapi()["paths"]) == ["/v1/shared", "/v2/shared"]
        assert unit(root, V1).shared is unit(root, V2).shared
