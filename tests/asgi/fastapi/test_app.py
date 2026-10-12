"""Web 应用单元：一个 FastAPI 应用，由依赖它的服务器服务。"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from canary_framework import Canary, asgi, dep, init
from canary_framework.asgi.fastapi import App, Router, get, mount
from canary_framework.test import running

pytestmark = pytest.mark.functional


class ReaderNotFoundError(Exception): ...


class ReaderApi(Router, prefix="/readers"):
    @get("/{reader_id}")
    async def get(self, reader_id: int) -> dict[str, int]:
        if reader_id > 9:
            raise ReaderNotFoundError(reader_id)
        return {"id": reader_id}


class LibraryApi(App, title="图书馆 API", version="1.0.0"):
    readers = dep(ReaderApi)

    @init
    def setup(self) -> None:
        self.app.add_exception_handler(ReaderNotFoundError, self.not_found)

    async def not_found(self, _: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"msg": f"no reader {exc}"}, status_code=404)

    @get
    async def index(self) -> dict[str, str]:
        return {"status": "ok"}


class Gateway(asgi.Server):
    api = dep(LibraryApi)
    port = 0


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_it_is_an_app_unit_that_does_not_listen() -> None:
    assert issubclass(App, asgi.App)
    assert not issubclass(App, asgi.Server)
    assert App.path == "/"


async def test_it_builds_a_fastapi_app_from_its_routers_without_any_server() -> None:
    async with running(LibraryApi) as api, _client(api.app) as client:
        assert isinstance(api.app, FastAPI)
        assert sorted(api.app.openapi()["paths"]) == ["/", "/readers/{reader_id}"]
        assert (await client.get("/readers/7")).json() == {"id": 7}
        assert (await client.get("/")).json() == {"status": "ok"}


async def test_class_parameters_configure_the_fastapi_app() -> None:
    class Staging(LibraryApi, title="预发"): ...

    assert Staging.__canary_app__ == {"title": "预发", "version": "1.0.0"}
    assert App.__canary_app__ == {}
    async with running(LibraryApi) as api:
        assert (api.app.title, api.app.version) == ("图书馆 API", "1.0.0")


async def test_the_app_can_still_be_configured_in_init() -> None:
    async with running(LibraryApi) as api, _client(api.app) as client:
        response = await client.get("/readers/99")
        assert (response.status_code, response.json()) == (404, {"msg": "no reader 99"})


async def test_a_server_that_depends_on_it_serves_it() -> None:
    async with running(Gateway) as gateway, httpx.AsyncClient() as client:
        url = f"http://127.0.0.1:{gateway.port}/readers/7"
        assert (await client.get(url)).json() == {"id": 7}


async def test_mount_puts_a_graph_of_routers_on_a_fastapi_app_of_your_own() -> None:
    class Root(Canary):
        readers = dep(ReaderApi)

    app = FastAPI()
    async with running(Root) as root, _client(app) as client:
        mount(root, app)
        assert (await client.get("/readers/3")).json() == {"id": 3}


async def test_a_served_app_can_be_restarted_without_duplicating_routes() -> None:
    gateway = Gateway()
    for _ in range(2):
        async with gateway, httpx.AsyncClient() as client:
            url = f"http://127.0.0.1:{gateway.port}/readers/1"
            assert (await client.get(url)).json() == {"id": 1}
            assert len(gateway.api.app.openapi()["paths"]) == 2
