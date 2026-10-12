"""What both sides of the protocol share: the type of an application, and dispatching by path.

协议两侧共用的东西：ASGI 应用的类型，以及按路径在若干应用之间分发。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from typing import Any

type _Message = MutableMapping[str, Any]

#: 一个 ASGI 应用：``async def app(scope, receive, send)``。
type Application = Callable[
    [
        MutableMapping[str, Any],
        Callable[[], Awaitable[_Message]],
        Callable[[_Message], Awaitable[None]],
    ],
    Awaitable[None],
]


def dispatch(routes: Mapping[str, Application]) -> Application:
    """Return one ASGI application that hands each request to the longest matching prefix.

    把若干 ASGI 应用按路径前缀合成一个::

        self.app = dispatch({"/metrics": self.metrics, "/": self.api})

    前缀按整段匹配：``/api`` 应答 ``/api`` 与 ``/api/...``，不应答 ``/apix``；``/`` 应答其余
    一切。最长的前缀优先。

    只做转发，**不改写** ``path`` 与 ``root_path``：每个应用看到的都是完整路径，因此它自己的
    路由要包含这个前缀。这不是"挂载"——挂载语义下子应用的根路径会被重定向到带斜杠的形式，
    而有些协议的端点恰好就在这个根上。

    没有前缀匹配时，HTTP 请求得到 404，WebSocket 连接被拒绝。lifespan 消息只作应答、不转发：
    应用单元的启动与回收归 Canary 的生命周期管。

    :raises ValueError: 某个前缀不以 ``/`` 开头，或两个前缀规范化之后相同。
    """
    table: dict[str, Application] = {}
    for prefix, app in routes.items():
        if not prefix.startswith("/"):
            raise ValueError(f"dispatch: {prefix!r} must start with '/'")
        key = prefix.rstrip("/") or "/"
        if key in table:
            raise ValueError(f"dispatch: {key!r} is given twice")
        table[key] = app
    # 最长的在前；``prefix + "/"`` 提前算好，不在每个请求上拼接。
    ordered = [
        (prefix, prefix + "/", app)
        for prefix, app in sorted(table.items(), key=lambda item: len(item[0]), reverse=True)
    ]

    async def dispatcher(
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[_Message]],
        send: Callable[[_Message], Awaitable[None]],
    ) -> None:
        kind = scope["type"]
        if kind == "lifespan":
            await _acknowledge(receive, send)
            return
        if kind not in ("http", "websocket"):
            return
        path = scope["path"]
        for prefix, below, app in ordered:
            if prefix == "/" or path == prefix or path.startswith(below):
                await app(scope, receive, send)
                return
        if kind == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = b"Not Found"
        headers = [(b"content-type", b"text/plain; charset=utf-8")]
        await send({"type": "http.response.start", "status": 404, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    return dispatcher


async def _acknowledge(
    receive: Callable[[], Awaitable[_Message]], send: Callable[[_Message], Awaitable[None]]
) -> None:
    """应答 lifespan 协议而不做任何事——驱动 lifespan 的服务器与测试客户端因此不会一直等。"""
    # 协议里启动与停止各一条；不写成循环，对方行为异常时也不会空转。
    message = await receive()
    if message["type"] == "lifespan.startup":
        await send({"type": "lifespan.startup.complete"})
        message = await receive()
    if message["type"] == "lifespan.shutdown":
        await send({"type": "lifespan.shutdown.complete"})
