"""The application unit.

应用单元：沿依赖图把接口拍平成一张表；它自己就是一个 ASGI 应用。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from canary_framework.core import Canary, LifecycleError, init, scope_of, start
from canary_framework.web.asgi import Application
from canary_framework.web.asgi.app.binding import invoke, respond
from canary_framework.web.asgi.app.http import HTTPError, Request, Response
from canary_framework.web.asgi.app.router import Table, collect
from canary_framework.web.asgi.app.routes import ERRORS, marked

_log = logging.getLogger("canary_framework.web.asgi.app")

type _Message = MutableMapping[str, Any]
type _Receive = Callable[[], Awaitable[_Message]]
type _Send = Callable[[_Message], Awaitable[None]]
type _Handlers = dict[type[Exception], Callable[..., Any]]


class App(Canary):
    """A unit that is an ASGI application, built from the routers it depends on.

    应用单元。它是一个单元，也是一个 ASGI 应用——``await app(scope, receive, send)``——所以
    任何 ASGI 服务器都能服务它::

        class LibraryApi(App):
            readers = dep(ReaderApi)
            loans = dep(LoanApi)

            @error(DomainError)
            async def on_domain_error(self, request: Request, exc: DomainError) -> Response:
                return Response.json({"msg": exc.message}, status=exc.code)

    **交给本包的服务器单元**——图由 Canary 驱动，监听是生命周期的一部分::

        class Gateway(Server):
            api = dep(LibraryApi)
            port = 8010

        async with Gateway():
            ...

    **交给别的 ASGI 服务器**——图由服务器的 lifespan 消息驱动：启动时这个单元连同它的依赖
    按序 ``init``、``start``，停止时逆序回收::

        app = LibraryApi()          # main.py
        # $ uvicorn main:app --reload

    ``@init`` 沿依赖图收集自己的接口与它直接依赖的路由单元的接口，拍平成一张表。路径重复、
    签名无法绑定之类的问题在这一步就抛出 ``DeclarationError``，不会留到请求到来时。

    请求交给 :attr:`app`。子类的 ``@init`` 在它建好之后运行，可以给它包上任意 ASGI 中间件::

        @init
        def wrap(self) -> None:
            self.app = CORSMiddleware(self.app, allow_origins=["*"])
    """

    #: 被服务器单元服务时应答的路径前缀。请求按最长前缀分发，应用看到的仍是完整路径。
    path: str = "/"
    #: 处理请求的 ASGI 应用，``@init`` 之后可用。可以在子类的 ``@init`` 里包上中间件。
    app: Application

    async def __call__(
        self, scope: MutableMapping[str, Any], receive: _Receive, send: _Send
    ) -> None:
        """The ASGI entry point.

        ASGI 入口。请求交给 :attr:`app`；lifespan 消息用来启动与回收这个单元所在的图。

        :raises LifecycleError: 单元还没有 ``init``——既没有被 Canary 启动，服务器也没有发过
            lifespan 消息。
        """
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        try:
            app = self.app
        except AttributeError:
            raise LifecycleError(
                f"{type(self).__name__} was asked to serve before its lifecycle began. "
                f"Start it ('async with app:', or a Server unit that depends on it), "
                f"or let the ASGI server send lifespan messages."
            ) from None
        await app(scope, receive, send)

    async def _lifespan(self, receive: _Receive, send: _Send) -> None:
        """由服务器的 lifespan 消息驱动这张图；已经由 Canary 启动的，只应答、不重复驱动。"""
        owns = False
        message = await receive()
        if message["type"] == "lifespan.startup":
            owns = type(self) not in scope_of(self).entered(start)
            if owns:
                try:
                    await self.__aenter__()
                except Exception as exc:
                    _log.error("%s failed to start", type(self).__name__, exc_info=exc)
                    failure = f"{type(exc).__name__}: {exc}"
                    await send({"type": "lifespan.startup.failed", "message": failure})
                    return
            await send({"type": "lifespan.startup.complete"})
            message = await receive()
        if message["type"] == "lifespan.shutdown":
            if owns:
                try:
                    await self.stop()
                except Exception as exc:
                    _log.error("%s failed to stop", type(self).__name__, exc_info=exc)
                    failure = f"{type(exc).__name__}: {exc}"
                    await send({"type": "lifespan.shutdown.failed", "message": failure})
                    return
            await send({"type": "lifespan.shutdown.complete"})

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
