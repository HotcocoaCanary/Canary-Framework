"""按路径分发：把若干 ASGI 应用合成一个。"""

from __future__ import annotations

from typing import Any

import pytest

from canary_framework.web.asgi import Application, dispatch

pytestmark = pytest.mark.unit


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
    assert await _call(dispatch({"/": says("root")}), "", "something-else") == []


async def test_lifespan_is_acknowledged_and_not_forwarded() -> None:
    """驱动 lifespan 的服务器与测试客户端在等这两声应答；应用单元的生命周期归 Canary。"""
    incoming = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])
    sent: list[Any] = []

    async def receive() -> dict[str, Any]:
        return next(incoming)

    async def send(message: Any) -> None:
        sent.append(message["type"])

    await dispatch({"/": says("root")})({"type": "lifespan"}, receive, send)
    assert sent == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


def test_bad_prefixes_are_rejected_when_dispatch_is_built() -> None:
    with pytest.raises(ValueError, match="must start with '/'"):
        dispatch({"api": says("api")})
    with pytest.raises(ValueError, match="'/api' is given twice"):
        dispatch({"/api": says("a"), "/api/": says("b")})
