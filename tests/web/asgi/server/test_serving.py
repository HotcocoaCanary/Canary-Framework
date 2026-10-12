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
    """手写的应用单元：一个可调用的单元。服务器只认这一点，外加可选的 ``path``。"""

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
    """可调用的依赖是应用，各自应答自己的 ``path``（没有就是 ``/``）；``Database`` 不可调用，不算。"""
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
