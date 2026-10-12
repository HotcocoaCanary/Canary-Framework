"""依赖即服务：服务器服务它直接依赖的应用单元，不问它们是怎么来的。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from canary_framework import Canary, LifecycleError, dep, init, start, stop
from canary_framework.test import running
from canary_framework.web.asgi import Application, dispatch
from canary_framework.web.asgi.server import Server

pytestmark = pytest.mark.functional

events: list[str] = []


def says(text: str) -> Application:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        body = f"{text} {scope['path']}".encode()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": body})

    return app


@pytest.fixture(autouse=True)
def _clear() -> None:
    events.clear()


class Database(Canary):
    @start
    def connect(self) -> None:
        events.append("db start")

    @stop
    def close(self) -> None:
        events.append("db stop")


class Raw(Canary):
    """手写的应用单元：可调用，并且声明了 ``path``。服务器只认这两点。"""

    path = "/"
    text = ""

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await says(self.text)(scope, receive, send)


class Api(Raw):
    database = dep(Database)

    text = "api"

    @start
    def warm(self) -> None:
        events.append("api start")

    @stop
    def cool(self) -> None:
        events.append("api stop")


class Metrics(Raw):
    path = "/metrics"
    text = "metrics"


class Gateway(Server):
    api = dep(Api)
    metrics = dep(Metrics)
    database = dep(Database)

    port = 0

    @start
    def announce(self) -> None:
        events.append("listening")


def _url(server: Server, path: str) -> str:
    return f"http://{server.host}:{server.port}{path}"


async def test_a_server_serves_every_app_unit_it_depends_on_on_one_port() -> None:
    """可调用并声明了 ``path`` 的依赖是应用，各自应答自己的 ``path``；``Database`` 不算。"""
    async with running(Gateway) as gateway, httpx.AsyncClient() as client:
        assert (await client.get(_url(gateway, "/readers"))).text.startswith("api /readers")
        assert (await client.get(_url(gateway, "/metrics"))).text.startswith("metrics /metrics")


async def test_apps_are_ready_before_it_listens_and_outlive_it() -> None:
    async with running(Gateway):
        assert events == ["db start", "api start", "listening"]
    assert events == ["db start", "api start", "listening", "api stop", "db stop"]


async def test_an_app_unit_is_one_instance_however_many_servers_serve_it() -> None:
    class Public(Server):
        api = dep(Api)
        port = 0

    class Internal(Server):
        api = dep(Api)
        metrics = dep(Metrics)
        port = 0

    class Both(Canary):
        public = dep(Public)
        internal = dep(Internal)

    async with running(Both) as both, httpx.AsyncClient() as client:
        assert both.public.api is both.internal.api
        assert both.public.port != both.internal.port
        assert (await client.get(_url(both.public, "/x"))).text.startswith("api")
        assert (await client.get(_url(both.public, "/metrics"))).text.startswith("api")
        assert (await client.get(_url(both.internal, "/metrics"))).text.startswith("metrics")
    assert events.count("api start") == 1


async def test_only_app_units_depended_on_directly_are_served() -> None:
    class Holder(Canary):
        metrics = dep(Metrics)

    class Narrow(Server):
        api = dep(Api)
        holder = dep(Holder)
        port = 0

    async with running(Narrow) as server, httpx.AsyncClient() as client:
        assert (await client.get(_url(server, "/metrics"))).text.startswith("api /metrics")


async def test_an_app_assigned_explicitly_wins_over_the_app_units() -> None:
    class Manual(Server):
        api = dep(Api)
        metrics = dep(Metrics)
        port = 0

        @init
        def build(self) -> None:
            self.app = dispatch({"/m": self.metrics, "/": self.api})

    async with running(Manual) as server, httpx.AsyncClient() as client:
        assert (await client.get(_url(server, "/m"))).text.startswith("metrics /m")
        assert (await client.get(_url(server, "/metrics"))).text.startswith("api /metrics")


async def test_two_apps_on_one_path_fail_the_start() -> None:
    class Other(Raw):
        text = "other"

    class Clash(Server):
        api = dep(Api)
        other = dep(Other)
        port = 0

    with pytest.raises(LifecycleError, match=r"two apps answer '/'"):
        async with Clash():
            raise AssertionError("unreachable")
    assert events == ["db start", "api start", "api stop", "db stop"]


async def test_the_gateway_can_be_restarted() -> None:
    gateway = Gateway()
    for _ in range(2):
        async with gateway, httpx.AsyncClient() as client:
            assert (await client.get(_url(gateway, "/metrics"))).status_code == 200


async def test_it_serves_an_application_from_another_framework() -> None:
    """服务器只认协议：一个原生的 FastAPI 对象，赋给 ``self.app`` 就能被服务。"""
    from fastapi import FastAPI

    fastapi_app = FastAPI()

    @fastapi_app.get("/hello")
    async def hello() -> dict[str, str]:
        return {"from": "fastapi"}

    class Foreign(Server):
        port = 0

        @init
        def build(self) -> None:
            self.app = fastapi_app

    async with running(Foreign) as server, httpx.AsyncClient() as client:
        assert (await client.get(_url(server, "/hello"))).json() == {"from": "fastapi"}


async def test_a_callable_collaborator_without_a_path_is_not_an_application() -> None:
    """恰好可调用的普通依赖（策略、工厂）不会被挂到端口上；有 ``path`` 而不可调用的也不会。"""

    class Strategy(Canary):
        def __call__(self, amount: int) -> int:
            return amount * 2

    class Labelled(Canary):
        path = "/labelled"

    class Narrow(Server):
        metrics = dep(Metrics)
        strategy = dep(Strategy)
        labelled = dep(Labelled)
        port = 0

    async with running(Narrow) as server, httpx.AsyncClient() as client:
        assert server.strategy(21) == 42
        assert (await client.get(_url(server, "/metrics"))).status_code == 200
        assert (await client.get(_url(server, "/"))).status_code == 404
        assert (await client.get(_url(server, "/labelled"))).status_code == 404


async def test_lifespan_can_be_turned_on_for_an_application_that_relies_on_it() -> None:
    """默认不发 lifespan 消息；``lifespan="on"`` 时别的框架的应用照常启动与回收自己的东西。"""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    def build(ran: list[str]) -> FastAPI:
        @asynccontextmanager
        async def lifespan(_: FastAPI) -> Any:
            ran.append("startup")
            yield
            ran.append("shutdown")

        return FastAPI(lifespan=lifespan)

    silent: list[str] = []
    driven: list[str] = []

    class Silent(Server):
        port = 0

        @init
        def build(self) -> None:
            self.app = build(silent)

    class Driven(Server, lifespan="on"):
        port = 0

        @init
        def build(self) -> None:
            self.app = build(driven)

    async with running(Silent), running(Driven):
        assert (silent, driven) == ([], ["startup"])
    assert (silent, driven) == ([], ["startup", "shutdown"])


async def test_with_lifespan_on_the_application_units_are_not_driven_twice() -> None:
    """应用单元已由 Canary 启动；服务器再发 lifespan 消息时，分发层只应答。"""

    class Loud(Server, lifespan="on"):
        api = dep(Api)
        port = 0

    async with running(Loud) as server, httpx.AsyncClient() as client:
        assert (await client.get(_url(server, "/x"))).status_code == 200
    assert events == ["db start", "api start", "api stop", "db stop"]


async def test_an_application_whose_lifespan_fails_fails_the_start() -> None:
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Any:
        raise RuntimeError("连不上数据库")
        yield

    class Broken(Server, lifespan="on"):
        database = dep(Database)
        port = 0

        @init
        def build(self) -> None:
            self.app = FastAPI(lifespan=lifespan)

    with pytest.raises(RuntimeError, match="lifespan failed during startup"):
        async with Broken():
            raise AssertionError("unreachable")
    assert events == ["db start", "db stop"], "已启动的依赖照常回收"
