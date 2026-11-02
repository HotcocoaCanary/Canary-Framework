"""WebSocket 接口：标记、绑定、收发、关闭，以及握手前后的出错。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import MutableMapping
from typing import Any

import httpx
import pytest
import websockets
from pydantic import BaseModel

from canary_framework import Canary, DeclarationError, dep, init
from canary_framework.test import running
from canary_framework.web.asgi.app import (
    App,
    HTTPError,
    Request,
    Router,
    WebSocket,
    WebSocketClosedError,
    get,
    websocket,
)
from canary_framework.web.asgi.server import Server

pytestmark = pytest.mark.functional

_EXT: dict[str, Any] = {"websocket.http.response": {}}


class Note(BaseModel):
    text: str


class Rooms(Canary):
    @init
    def seed(self) -> None:
        self.left: list[str] = []


class RoomApi(Router, prefix="/rooms"):
    rooms = dep(Rooms)

    @get("/{room}")
    async def show(self, room: str) -> str:
        return room

    @websocket("/{room}")
    async def chat(self, socket: WebSocket, room: str, times: int = 1) -> None:
        try:
            async for message in socket:
                for _ in range(times):
                    await socket.send(f"{room}: {message!s}")
        finally:
            self.rooms.left.append(room)

    @websocket("/json")
    async def notes(self, socket: WebSocket) -> None:
        note = Note.model_validate_json(await socket.receive())
        await socket.send_json(Note(text=note.text.upper()))

    @websocket("/bytes")
    async def raw(self, socket: WebSocket) -> None:
        data = await socket.receive()
        assert isinstance(data, bytes)
        await socket.send(data[::-1])


class Chat(App):
    rooms = dep(RoomApi)

    @websocket
    async def root(self, socket: WebSocket) -> None:
        await socket.accept("v2", headers={"X-Room": "lobby"})
        await socket.send(socket.headers.get("user-agent", ""))

    @websocket("/guarded")
    async def guarded(self, socket: WebSocket, token: str = "") -> None:
        if token != "secret":
            raise HTTPError(403, "bad token")
        await socket.send("in")

    @websocket("/refused")
    async def refused(self, socket: WebSocket) -> None:
        await socket.close(4001, "go away")

    @websocket("/broken")
    async def broken(self, socket: WebSocket, early: bool = False) -> None:
        if not early:
            await socket.send("hello")
        raise RuntimeError("boom")

    @websocket("/quiet")
    async def quiet(self, socket: WebSocket) -> None:
        await socket.send("bye")

    @get("/plain")
    async def plain(self) -> str:
        return "plain"

    @websocket("/rude")
    async def rude(self, socket: WebSocket) -> None:
        await socket.send("one")
        await socket.send("two")


class Peer:
    """一个假的 ASGI 服务器端：按顺序喂入消息，记下应用发出的。"""

    def __init__(self, *incoming: dict[str, Any]) -> None:
        self.incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for message in incoming:
            self.incoming.put_nowait(message)
        self.sent: list[MutableMapping[str, Any]] = []

    async def receive(self) -> dict[str, Any]:
        return await self.incoming.get()

    async def send(self, message: MutableMapping[str, Any]) -> None:
        self.sent.append(message)


def _scope(path: str, query: bytes = b"", extensions: dict[str, Any] | None = None) -> Any:
    return {
        "type": "websocket",
        "path": path,
        "query_string": query,
        "headers": [(b"user-agent", b"probe")],
        "extensions": extensions or {},
    }


def _text(text: str) -> dict[str, Any]:
    return {"type": "websocket.receive", "text": text}


CONNECT = {"type": "websocket.connect"}
LEAVE = {"type": "websocket.disconnect", "code": 1001}


async def _talk(app: Any, peer: Peer, path: str, query: bytes = b"", **kw: Any) -> list[Any]:
    await app(_scope(path, query, **kw), peer.receive, peer.send)
    return peer.sent


# --- 收发与绑定 ---------------------------------------------------------------


async def test_messages_are_echoed_with_path_and_query_bound_and_leaving_ends_quietly() -> None:
    async with running(Chat) as chat:
        peer = Peer(CONNECT, _text("hi"), _text("yo"), LEAVE)
        sent = await _talk(chat, peer, "/rooms/a", b"times=2")
        assert sent == [
            {"type": "websocket.accept"},
            {"type": "websocket.send", "text": "a: hi"},
            {"type": "websocket.send", "text": "a: hi"},
            {"type": "websocket.send", "text": "a: yo"},
            {"type": "websocket.send", "text": "a: yo"},
        ]
        assert chat.rooms.rooms.left == ["a"]


async def test_json_and_bytes() -> None:
    async with running(Chat) as chat:
        sent = await _talk(chat, Peer(CONNECT, _text('{"text": "hi"}')), "/rooms/json")
        assert sent[1] == {"type": "websocket.send", "text": '{"text":"HI"}'}
        assert sent[-1] == {"type": "websocket.close", "code": 1000}

        incoming = {"type": "websocket.receive", "bytes": b"abc"}
        sent = await _talk(chat, Peer(CONNECT, incoming), "/rooms/bytes")
        assert sent[1] == {"type": "websocket.send", "bytes": b"cba"}


async def test_explicit_accept_takes_a_subprotocol_and_headers_and_sees_request_headers() -> None:
    async with running(Chat) as chat:
        sent = await _talk(chat, Peer(CONNECT), "/")
        assert sent == [
            {"type": "websocket.accept", "subprotocol": "v2", "headers": [(b"x-room", b"lobby")]},
            {"type": "websocket.send", "text": "probe"},
            {"type": "websocket.close", "code": 1000},
        ]


async def test_a_socket_cannot_be_used_after_it_is_closed() -> None:
    peer = Peer(CONNECT)
    socket = WebSocket(_scope("/"), peer.receive, peer.send)
    await socket.accept()
    with pytest.raises(RuntimeError):
        await socket.accept()
    await socket.close()
    await socket.close()  # 第二次什么也不做
    assert socket.closed
    with pytest.raises(WebSocketClosedError):
        await socket.send("late")
    with pytest.raises(WebSocketClosedError):
        await socket.receive()
    assert peer.sent == [{"type": "websocket.accept"}, {"type": "websocket.close", "code": 1000}]


async def test_a_send_after_the_client_left_is_a_disconnect() -> None:
    class Gone(Peer):
        async def send(self, message: MutableMapping[str, Any]) -> None:
            if message["type"] == "websocket.send" and self.sent:
                raise OSError("client disconnected")  # uvicorn 的 ClientDisconnected
            await super().send(message)

    async with running(Chat) as chat:
        sent = await _talk(chat, Gone(CONNECT), "/rude")
        assert sent == [{"type": "websocket.accept"}]  # 不再尝试关闭


# --- 握手与出错 ---------------------------------------------------------------


async def test_without_the_extension_a_failed_handshake_is_refused() -> None:
    async with running(Chat) as chat:
        assert await _talk(chat, Peer(CONNECT), "/nowhere") == [
            {"type": "websocket.close", "code": 1008}
        ]
        assert await _talk(chat, Peer(CONNECT), "/guarded") == [
            {"type": "websocket.close", "code": 1008}
        ]
        assert await _talk(chat, Peer(CONNECT), "/refused") == [
            {"type": "websocket.close", "code": 4001, "reason": "go away"}
        ]


async def test_with_the_extension_a_failed_handshake_is_answered_like_http() -> None:
    async with running(Chat) as chat:
        sent = await _talk(chat, Peer(CONNECT), "/nowhere", extensions=_EXT)
        assert sent[0]["type"] == "websocket.http.response.start"
        assert sent[0]["status"] == 404
        assert sent[1] == {
            "type": "websocket.http.response.body",
            "body": b'{"detail":"Not Found"}',
        }

        sent = await _talk(chat, Peer(CONNECT), "/guarded", extensions=_EXT)
        assert sent[0]["status"] == 403
        assert sent[1]["body"] == b'{"detail":"bad token"}'

        sent = await _talk(chat, Peer(CONNECT), "/rooms/a", b"times=x", extensions=_EXT)
        assert sent[0]["status"] == 422
        assert b'"loc":["query","times"]' in sent[1]["body"]


async def test_the_http_and_websocket_tables_are_separate() -> None:
    async with running(Chat) as chat:
        # 只有 HTTP 接口的路径不接受 WebSocket，反之亦然……
        sent = await _talk(chat, Peer(CONNECT), "/plain", extensions=_EXT)
        assert sent[0]["status"] == 404
        transport = httpx.ASGITransport(app=chat)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            assert (await http.get("/guarded")).status_code == 404
            # ……同一路径两者都有时各走各的
            assert (await http.get("/rooms/a")).json() == "a"
        sent = await _talk(chat, Peer(CONNECT, LEAVE), "/rooms/a")
        assert sent == [{"type": "websocket.accept"}]


async def test_a_failure_is_logged_and_closes_with_1011_or_answers_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with running(Chat) as chat:
        with caplog.at_level(logging.ERROR, "canary_framework.web.asgi.app"):
            sent = await _talk(chat, Peer(CONNECT), "/broken")
        assert sent[-1] == {"type": "websocket.close", "code": 1011}
        assert "WEBSOCKET /broken failed" in caplog.text

        sent = await _talk(chat, Peer(CONNECT), "/broken", b"early=1", extensions=_EXT)
        assert sent[0]["status"] == 500


async def test_the_client_leaving_during_the_handshake_ends_quietly() -> None:
    async with running(Chat) as chat:
        assert await _talk(chat, Peer(LEAVE), "/quiet") == []


# --- 接口表与声明 -------------------------------------------------------------


async def test_websocket_endpoints_are_in_the_table_in_declaration_order() -> None:
    async with running(Chat) as chat:
        table = [(e.method, e.path) for e in chat.endpoints]
    assert table[:3] == [("WEBSOCKET", "/"), ("WEBSOCKET", "/guarded"), ("WEBSOCKET", "/refused")]
    assert ("GET", "/plain") in table
    assert ("GET", "/rooms/{room}") in table
    assert ("WEBSOCKET", "/rooms/{room}") in table
    chat_endpoint = next(e for e in chat.endpoints if e.name == "RoomApi.chat")
    assert [(p.name, p.source) for p in chat_endpoint.params] == [
        ("socket", "websocket"),
        ("room", "path"),
        ("times", "query"),
    ]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("def handle(self, socket: WebSocket) -> None: ...", "must be 'async def'"),
        ("async def handle(self, body: bytes) -> None: ...", "has no body"),
        ("async def handle(self, request: Request) -> None: ...", "has no request"),
    ],
)
async def test_what_a_websocket_endpoint_cannot_be(body: str, message: str) -> None:
    namespace: dict[str, Any] = {"WebSocket": WebSocket, "Request": Request}
    exec(body, namespace)
    handle = websocket("/x")(namespace["handle"])
    broken = type("Broken", (App,), {"handle": handle, "__module__": __name__})
    with pytest.raises(DeclarationError, match=message):
        async with running(broken):
            pass


async def test_an_http_endpoint_cannot_take_a_websocket_and_paths_are_checked() -> None:
    class Wrong(App):
        @get("/x")
        async def handle(self, socket: WebSocket) -> None: ...

    with pytest.raises(DeclarationError, match="only a @websocket endpoint"):
        async with running(Wrong):
            pass

    with pytest.raises(DeclarationError, match="starts with '/'"):
        websocket("x")

    class Twice(App):
        @websocket("/x")
        async def one(self, socket: WebSocket) -> None: ...

        @websocket("/x")
        async def two(self, socket: WebSocket) -> None: ...

    with pytest.raises(DeclarationError, match="WEBSOCKET /x is answered twice"):
        async with running(Twice):
            pass


# --- 经过真正的服务器 ---------------------------------------------------------


class Gateway(Server, timeout_graceful_shutdown=2):
    chat = dep(Chat)
    port = 0


async def test_over_a_real_server() -> None:
    async with running(Gateway) as gateway:
        url = f"ws://127.0.0.1:{gateway.port}"
        async with websockets.connect(f"{url}/rooms/a") as client:
            await client.send("hi")
            assert await client.recv() == "a: hi"
        async with websockets.connect(f"{url}/", subprotocols=["v2"]) as client:  # type: ignore[list-item]
            assert client.subprotocol == "v2"
            assert client.response is not None
            assert client.response.headers["x-room"] == "lobby"
        with pytest.raises(websockets.InvalidStatus) as refused:
            await websockets.connect(f"{url}/guarded")
        assert refused.value.response.status_code == 403
        assert refused.value.response.body == b'{"detail":"bad token"}'
        # 停机时还连着的客户端收到 1012，停机不被它卡住
        client = await websockets.connect(f"{url}/rooms/b")
    with pytest.raises(websockets.ConnectionClosed) as closed:
        await client.recv()
    assert closed.value.rcvd is not None
    assert closed.value.rcvd.code == 1012


async def test_a_refused_handshake_is_not_logged_as_a_server_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """服务器单元默认的 WebSocket 实现（wsproto）把以 HTTP 响应拒绝握手当作正常结束。"""
    with caplog.at_level(logging.ERROR, "uvicorn.error"):
        async with running(Gateway) as gateway:
            with pytest.raises(websockets.InvalidStatus):
                await websockets.connect(f"ws://127.0.0.1:{gateway.port}/guarded")
    assert [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"] == []
