"""The web application unit.

Web 应用单元：沿依赖图把接口拍平成一张表，自己不监听。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from canary_framework import asgi
from canary_framework.asgi.web.binding import invoke, respond
from canary_framework.asgi.web.http import HTTPError, Request, Response
from canary_framework.asgi.web.router import Table, collect
from canary_framework.asgi.web.routes import ERRORS, marked
from canary_framework.core import init

_log = logging.getLogger("canary_framework.asgi.web")

type _Message = MutableMapping[str, Any]
type _Handlers = dict[type[Exception], Callable[..., Any]]


class App(asgi.App):
    """A unit that is a web application built from the routers it depends on.

    Web 应用单元::

        class LibraryApi(App):
            readers = dep(ReaderApi)
            loans = dep(LoanApi)

            @error(DomainError)
            async def on_domain_error(self, request: Request, exc: DomainError) -> Response:
                return Response.json({"msg": exc.message}, status=exc.code)

        class Gateway(asgi.Server):
            api = dep(LibraryApi)
            port = 8010

    ``@init`` 沿依赖图收集自己的接口与它直接依赖的路由单元的接口，拍平成一张表，建出
    ASGI 应用 :attr:`app`。路径重复、签名无法绑定之类的问题在这一步就抛出
    ``DeclarationError``，不会留到请求到来时。

    子类的 ``@init`` 在此之后运行，可以给 :attr:`app` 包上任意 ASGI 中间件::

        @init
        def wrap(self) -> None:
            self.app = CORSMiddleware(self.app, allow_origins=["*"])

    它自己不监听：哪个 :class:`canary_framework.asgi.Server` 直接依赖它，它就在那个端口上。
    """

    @init
    def _assemble(self) -> None:
        table = Table()
        for path, route, call in collect(self):
            table.add(path, route, call)
        handlers: _Handlers = {}
        for call, types in marked(self, ERRORS):
            handlers.update(dict.fromkeys(types, call))
        self.app = _Web(table, handlers)


class _Web:
    """ASGI 应用本身：查表、调用接口、把异常变成响应。"""

    __slots__ = ("_handlers", "_table")

    def __init__(self, table: Table, handlers: _Handlers) -> None:
        self._table = table
        self._handlers = handlers

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[_Message]],
        send: Callable[[_Message], Awaitable[None]],
    ) -> None:
        kind = scope["type"]
        if kind == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if kind != "http":
            return
        request = Request(scope, receive)
        try:
            response = await self._answer(request)
        except Exception as exc:
            response = await self._recover(request, exc)
        await response.send(send)

    async def _answer(self, request: Request) -> Response:
        found = self._table.find(request.scope["path"])
        if found is None:
            raise HTTPError(404)
        methods, values = found
        method = request.scope["method"]
        hit = methods.get(method)
        if hit is None and method == "HEAD":
            hit = methods.get("GET")
        if hit is None:
            raise HTTPError(405, headers={"allow": ", ".join(sorted(methods))})
        endpoint, names = hit
        if names:
            request.path_params = dict(zip(names, values, strict=True))
        return await endpoint(request)

    async def _recover(self, request: Request, exc: Exception) -> Response:
        """交给类型最贴近的处理器；没有处理器时，``HTTPError`` 按自身应答，其余应答 500。"""
        for klass in type(exc).__mro__:
            handler = self._handlers.get(klass)
            if handler is None:
                continue
            try:
                return respond(await invoke(handler, request, exc))
            except Exception as failure:
                exc = failure
                break
        if isinstance(exc, HTTPError):
            return Response.json({"detail": exc.detail}, status=exc.status, headers=exc.headers)
        _log.error("%s %s failed", request.method, request.path, exc_info=exc)
        return Response.json({"detail": "Internal Server Error"}, status=500)
