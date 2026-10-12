"""Application units, and dispatching between them by path.

应用单元，以及按路径在它们之间分发。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from typing import Any

from canary_framework.core import Canary

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


class App(Canary):
    """A unit that is one ASGI application, served by whichever server depends on it.

    应用单元：它是一个 ASGI 应用，自己不监听。哪个 :class:`~canary_framework.asgi.Server`
    直接依赖它，它就在那个端口上被服务::

        class Metrics(App):
            path = "/metrics"

            @init
            def build(self) -> None:
                self.app = make_asgi_app()

        class Gateway(Server):
            api = dep(LibraryApi)           # 一个 FastAPI 应用单元，应答 /
            metrics = dep(Metrics)          # 应答 /metrics
            port = 8010

    应用是值，端口才需要唯一：一个进程里可以有很多应用单元，监听的只有依赖它们的那个服务器。
    应用需要的启动与回收写成它自己的 ``@start`` / ``@stop``——它是被依赖的一方，所以自然
    先于监听就绪、晚于监听关闭。
    """

    #: 本应用应答的路径前缀。请求按最长前缀分发，应用看到的仍是完整路径。
    path: str = "/"
    #: ASGI 应用本身，由子类在 ``@init`` 里赋值。
    app: Application


def dispatch(routes: Mapping[str, Application]) -> Application:
    """Return one ASGI application that hands each request to the longest matching prefix.

    把若干 ASGI 应用按路径前缀合成一个::

        self.app = dispatch({"/metrics": self.metrics.app, "/": self.api.app})

    前缀按整段匹配：``/api`` 应答 ``/api`` 与 ``/api/...``，不应答 ``/apix``；``/`` 应答其余
    一切。最长的前缀优先。

    只做转发，**不改写** ``path`` 与 ``root_path``：每个应用看到的都是完整路径，因此它自己的
    路由要包含这个前缀。这不是"挂载"——挂载语义下子应用的根路径会被重定向到带斜杠的形式，
    而有些协议的端点恰好就在这个根上。

    没有前缀匹配时，HTTP 请求得到 404，WebSocket 连接被拒绝。

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
    ordered = sorted(table.items(), key=lambda item: len(item[0]), reverse=True)

    async def dispatcher(
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[_Message]],
        send: Callable[[_Message], Awaitable[None]],
    ) -> None:
        kind = scope["type"]
        if kind not in ("http", "websocket"):
            return
        path = scope["path"]
        for prefix, app in ordered:
            if prefix == "/" or path == prefix or path.startswith(prefix + "/"):
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
