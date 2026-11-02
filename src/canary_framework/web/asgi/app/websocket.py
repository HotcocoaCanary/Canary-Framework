"""WebSocket connections.

WebSocket 连接：接受、收发、关闭，以及对端离开时的那个异常。
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, MutableMapping
from typing import Any

from pydantic_core import to_json

from canary_framework.web.asgi.app.http import Connection

type _Message = MutableMapping[str, Any]
type _Receive = Callable[[], Awaitable[_Message]]
type _Send = Callable[[_Message], Awaitable[None]]

_CONNECTING, _OPEN, _CLOSED = 0, 1, 2


class WebSocketClosedError(Exception):
    """The connection is gone: the client left, or it was already closed.

    连接已经断开：对端离开了，或者它早已关闭。在 WebSocket 接口里不必捕获——框架把它当作
    正常结束。

    :param code: 关闭码。对端没有给出时是 1005，连接异常中断时是 1006。
    :param reason: 对端给出的关闭原因。
    """

    def __init__(self, code: int = 1000, reason: str = "") -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"{code}: {reason}" if reason else str(code))


class WebSocket(Connection):
    """One WebSocket connection.

    一个 WebSocket 连接。WebSocket 接口里写一个注解为 ``WebSocket`` 的形参就能拿到它::

        @websocket("/{room}")
        async def chat(self, socket: WebSocket, room: str) -> None:
            async for message in socket:
                await socket.send(f"{room}: {message}")

    第一次收发时自动接受连接；要选子协议或附加响应头时自己先调用 :meth:`accept`。接受之前
    调用 :meth:`close` 或抛出 ``HTTPError`` 就是拒绝这次握手。接口返回时连接若还开着，框架
    以 1000 关闭它。

    请求头、查询参数、路径参数与 :class:`Request` 一样从这里读。
    """

    __slots__ = ("_receive", "_send", "_state")

    def __init__(self, scope: MutableMapping[str, Any], receive: _Receive, send: _Send) -> None:
        super().__init__(scope)
        self._receive = receive
        self._send = send
        self._state = _CONNECTING

    @property
    def _connecting(self) -> bool:
        """握手还没有应答：既没接受，也没拒绝。"""
        return self._state == _CONNECTING

    @property
    def closed(self) -> bool:
        """连接是否已经关闭，无论是哪一方关的。"""
        return self._state == _CLOSED

    async def accept(
        self, subprotocol: str | None = None, *, headers: Mapping[str, str] | None = None
    ) -> None:
        """Accept the handshake.

        接受握手。

        :param subprotocol: 选定的子协议，须是客户端提出过的之一。
        :param headers: 附加在握手响应上的头。
        :raises RuntimeError: 已经接受过，或已经关闭。
        :raises WebSocketClosedError: 握手完成前对端就离开了。
        """
        if self._state != _CONNECTING:
            raise RuntimeError("WebSocket.accept(): the connection was already accepted or closed")
        message = await self._receive()
        if message["type"] == "websocket.disconnect":
            self._state = _CLOSED
            raise WebSocketClosedError(message.get("code", 1006), message.get("reason") or "")
        accept: _Message = {"type": "websocket.accept"}
        if subprotocol is not None:
            accept["subprotocol"] = subprotocol
        if headers:
            accept["headers"] = [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in headers.items()
            ]
        await self._send(accept)
        self._state = _OPEN

    async def receive(self) -> str | bytes:
        """Wait for the next message: ``str`` for a text frame, ``bytes`` for a binary one.

        等下一条消息：文本帧是 ``str``，二进制帧是 ``bytes``。JSON 自己解析，比如
        ``Message.model_validate_json(await socket.receive())``。

        :raises WebSocketClosedError: 对端离开了，或连接已经关闭。
        """
        if self._state == _CONNECTING:
            await self.accept()
        elif self._state == _CLOSED:
            raise WebSocketClosedError(1006, "the connection is closed")
        message = await self._receive()
        if message["type"] == "websocket.disconnect":
            self._state = _CLOSED
            raise WebSocketClosedError(message.get("code", 1005), message.get("reason") or "")
        text: str | None = message.get("text")
        if text is not None:
            return text
        data: bytes = message.get("bytes") or b""
        return data

    async def send(self, data: str | bytes) -> None:
        """Send one message: ``str`` as a text frame, ``bytes`` as a binary one.

        发一条消息：``str`` 是文本帧，``bytes`` 是二进制帧。

        :raises WebSocketClosedError: 对端已经离开，或连接已经关闭。
        """
        if self._state == _CONNECTING:
            await self.accept()
        elif self._state == _CLOSED:
            raise WebSocketClosedError(1006, "the connection is closed")
        message: _Message = (
            {"type": "websocket.send", "text": data}
            if isinstance(data, str)
            else {"type": "websocket.send", "bytes": data}
        )
        try:
            await self._send(message)
        except OSError:
            # 服务器在对端已经离开时这样报告（uvicorn 的 ClientDisconnected 是 OSError）。
            self._state = _CLOSED
            raise WebSocketClosedError(1006) from None

    async def send_json(self, data: Any) -> None:
        """Send *data* as JSON in a text frame. pydantic 模型、dataclass、日期等都能序列化。"""
        await self.send(to_json(data).decode())

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the connection; before it is accepted, this refuses the handshake.

        关闭连接；还没接受时，这就是拒绝握手（客户端看到 403）。已经关闭时什么也不做。
        """
        if self._state == _CLOSED:
            return
        self._state = _CLOSED
        message: _Message = {"type": "websocket.close", "code": code}
        if reason:
            message["reason"] = reason
        with contextlib.suppress(OSError):  # 对端已经走了，没什么可关的
            await self._send(message)

    def __aiter__(self) -> AsyncIterator[str | bytes]:
        """Every message until the client leaves. 对端离开时迭代正常结束。"""
        return self._messages()

    async def _messages(self) -> AsyncIterator[str | bytes]:
        while True:
            try:
                message = await self.receive()
            except WebSocketClosedError:
                return
            yield message
