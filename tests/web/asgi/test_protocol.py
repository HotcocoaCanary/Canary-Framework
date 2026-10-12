"""应用单元与按路径分发：应用是值，监听的是依赖它们的服务器。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from canary_framework import Canary, LifecycleError, dep, init, start, stop
from canary_framework.asgi import App, Application, Server, dispatch
from canary_framework.test import running

pytestmark = pytest.mark.functional

events: list[str] = []


def says(text: str) -> Application:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.send", "text": text})
            return
        body = f"{text} {scope['path']} root={scope.get('root_path', '')!r}".encode()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": body})

    return app


async def _call(app: Application, path: str, kind: str = "http") -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": f"{kind}.receive"}

    async def send(message: Any) -> None:
        sent.append(dict(message))

    await app({"type": kind, "path": path, "root_path": ""}, receive, send)
    return sent


async def _body(app: Application, path: str) -> tuple[int, str]:
    start_message, body = await _call(app, path)
    return start_message["status"], body["body"].decode()


@pytest.fixture(autouse=True)
def _clear() -> None:
    events.clear()


# ---------------------------------------------------------------- dispatch


async def test_the_longest_prefix_wins() -> None:
    app = dispatch({"/": says("root"), "/api": says("api"), "/api/v2": says("v2")})
    assert (await _body(app, "/"))[1].startswith("root /")
    assert (await _body(app, "/other"))[1].startswith("root /other")
    assert (await _body(app, "/api/readers"))[1].startswith("api /api/readers")
    assert (await _body(app, "/api/v2/readers"))[1].startswith("v2 /api/v2/readers")


async def test_a_prefix_matches_whole_segments_only() -> None:
    app = dispatch({"/mcp": says("mcp")})
    assert (await _body(app, "/mcp"))[0] == 200
    assert (await _body(app, "/mcp/session"))[0] == 200
    assert await _body(app, "/mcpx") == (404, "Not Found")
    assert await _body(app, "/") == (404, "Not Found")


async def test_the_app_sees_the_full_path_and_an_untouched_root_path() -> None:
    app = dispatch({"/mcp": says("mcp")})
    assert await _body(app, "/mcp/session") == (200, "mcp /mcp/session root=''")


async def test_a_trailing_slash_on_a_prefix_changes_nothing() -> None:
    app = dispatch({"/api/": says("api")})
    assert (await _body(app, "/api"))[0] == 200
    assert (await _body(app, "/api/x"))[0] == 200


async def test_websockets_are_dispatched_and_rejected_when_nothing_matches() -> None:
    app = dispatch({"/ws": says("hello")})
    assert [m["type"] for m in await _call(app, "/ws", "websocket")] == [
        "websocket.accept",
        "websocket.send",
    ]
    assert await _call(app, "/elsewhere", "websocket") == [
        {"type": "websocket.close", "code": 1008}
    ]


async def test_other_scopes_are_left_alone() -> None:
    assert await _call(dispatch({"/": says("root")}), "", "lifespan") == []


def test_bad_prefixes_are_rejected_when_dispatch_is_built() -> None:
    with pytest.raises(ValueError, match="must start with '/'"):
        dispatch({"api": says("api")})
    with pytest.raises(ValueError, match="'/api' is given twice"):
        dispatch({"/api": says("a"), "/api/": says("b")})


# ---------------------------------------------------------------- 应用单元


class Database(Canary):
    @start
    def connect(self) -> None:
        events.append("db start")

    @stop
    def close(self) -> None:
        events.append("db stop")


class Api(App):
    database = dep(Database)

    @init
    def build(self) -> None:
        self.app = says("api")

    @start
    def warm(self) -> None:
        events.append("api start")

    @stop
    def cool(self) -> None:
        events.append("api stop")


class Metrics(App):
    path = "/metrics"

    @init
    def build(self) -> None:
        self.app = says("metrics")


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
            self.app = dispatch({"/m": self.metrics.app, "/": self.api.app})

    async with running(Manual) as server, httpx.AsyncClient() as client:
        assert (await client.get(_url(server, "/m"))).text.startswith("metrics /m")
        assert (await client.get(_url(server, "/metrics"))).text.startswith("api /metrics")


async def test_two_apps_on_one_path_fail_the_start() -> None:
    class Other(App):
        @init
        def build(self) -> None:
            self.app = says("other")

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
