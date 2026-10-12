"""Requests, responses, and the error that becomes a response.

请求、响应，以及会变成响应的那个异常。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, MutableMapping
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

from pydantic_core import to_json

type _Message = MutableMapping[str, Any]
type _Receive = Callable[[], Awaitable[_Message]]
type _Send = Callable[[_Message], Awaitable[None]]

_JSON = "application/json"
_TEXT = "text/plain; charset=utf-8"
_BYTES = "application/octet-stream"


class HTTPError(Exception):
    """An error that is answered with a status code.

    会被应答成一个状态码的异常，在接口、服务或任何被调用到的地方抛出都可以::

        raise HTTPError(404, "no such reader")

    响应体是 ``{"detail": detail}``。路由不匹配（404）、方法不允许（405）、参数校验失败
    （422）也是它，所以 ``@error(HTTPError)`` 能统一改写它们的样子。

    :param status: HTTP 状态码。
    :param detail: 写进响应体的说明，任何能序列化成 JSON 的值。省略时是状态码的标准短语。
    :param headers: 附加的响应头。
    """

    def __init__(
        self, status: int, detail: Any = None, *, headers: Mapping[str, str] | None = None
    ) -> None:
        self.status = status
        self.detail = HTTPStatus(status).phrase if detail is None else detail
        self.headers = dict(headers or {})
        super().__init__(f"{status}: {self.detail}")


class Request:
    """One HTTP request.

    一次 HTTP 请求。接口方法里写一个注解为 ``Request`` 的形参就能拿到它::

        @get("/whoami")
        async def whoami(self, request: Request) -> dict[str, str]:
            return {"agent": request.headers.get("user-agent", "")}

    路径参数、查询参数与请求体通常直接写成形参；请求头、Cookie 与原始字节从这里读。
    """

    __slots__ = ("_body", "_headers", "_query", "_receive", "path_params", "scope")

    def __init__(self, scope: MutableMapping[str, Any], receive: _Receive) -> None:
        #: ASGI 的 scope，原样。
        self.scope = scope
        #: 路径参数，校验之前的字符串。
        self.path_params: dict[str, str] = {}
        self._receive = receive
        self._body: bytes | None = None
        self._headers: dict[str, str] | None = None
        self._query: dict[str, list[str]] | None = None

    @property
    def method(self) -> str:
        """HTTP 方法，大写。"""
        return str(self.scope["method"])

    @property
    def path(self) -> str:
        """请求路径，已解码，不含查询串。"""
        return str(self.scope["path"])

    @property
    def headers(self) -> Mapping[str, str]:
        """请求头，名字小写。同名的头用 ``", "`` 连接。"""
        if self._headers is None:
            headers: dict[str, str] = {}
            for raw_name, raw_value in self.scope["headers"]:
                name, value = raw_name.decode("latin-1"), raw_value.decode("latin-1")
                headers[name] = f"{headers[name]}, {value}" if name in headers else value
            self._headers = headers
        return self._headers

    @property
    def query(self) -> Mapping[str, list[str]]:
        """查询参数，每个名字对应它出现过的全部值。"""
        if self._query is None:
            raw = self.scope["query_string"].decode("latin-1")
            self._query = parse_qs(raw, keep_blank_values=True)
        return self._query

    async def body(self) -> bytes:
        """请求体的全部字节。读过一次之后是缓存。"""
        if self._body is None:
            chunks: list[bytes] = []
            while True:
                message = await self._receive()
                if message["type"] == "http.disconnect":
                    break
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            self._body = b"".join(chunks)
        return self._body


class Response:
    """One HTTP response.

    一次 HTTP 响应。接口方法通常直接返回数据，由框架序列化成 JSON；需要自己决定状态码、
    响应头或内容类型时返回它::

        return Response("pong")
        return Response.json({"id": 7}, status=201, headers={"location": "/readers/7"})
        return Response(self.events(), media_type="text/event-stream")

    :param body: ``bytes``、``str``，或一个逐块产出它们的异步迭代器（流式）。
    :param status: HTTP 状态码。
    :param headers: 响应头。
    :param media_type: ``content-type``。省略时 ``str`` 是纯文本，其余是字节流。
    """

    __slots__ = ("body", "headers", "status")

    def __init__(
        self,
        body: bytes | str | AsyncIterator[bytes | str] = b"",
        *,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> None:
        self.status = status
        self.headers = {name.lower(): value for name, value in (headers or {}).items()}
        if media_type is None:
            media_type = _TEXT if isinstance(body, str) else _BYTES
        self.headers.setdefault("content-type", media_type)
        self.body: bytes | AsyncIterator[bytes | str] = (
            body.encode() if isinstance(body, str) else body
        )

    @classmethod
    def json(
        cls, data: Any, *, status: int = 200, headers: Mapping[str, str] | None = None
    ) -> Response:
        """A JSON response. pydantic 模型、dataclass、日期等都能序列化。"""
        return cls(to_json(data), status=status, headers=headers, media_type=_JSON)

    async def send(self, send: _Send) -> None:
        """Write the response to an ASGI ``send``.

        把响应写给 ASGI 的 ``send``。
        """
        body = self.body
        headers = self.headers
        if isinstance(body, bytes):
            headers = {**headers, "content-length": str(len(body))}
        raw = [(name.encode("latin-1"), value.encode("latin-1")) for name, value in headers.items()]
        await send({"type": "http.response.start", "status": self.status, "headers": raw})
        if isinstance(body, bytes):
            await send({"type": "http.response.body", "body": body})
            return
        async for chunk in body:
            data = chunk.encode() if isinstance(chunk, str) else chunk
            await send({"type": "http.response.body", "body": data, "more_body": True})
        await send({"type": "http.response.body", "body": b""})
