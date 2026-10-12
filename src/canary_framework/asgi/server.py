"""The server unit.

服务器单元：监听端口是它的 ``@start``，关闭是它的 ``@stop``。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import socket
from collections.abc import Iterator

import uvicorn

from canary_framework.asgi.app import App, Application, dispatch
from canary_framework.core import Canary, LifecycleError, deps_of, scope_of, start, stop


class Server(Canary):
    """A unit that listens on one port and serves the applications it depends on.

    服务器单元：监听一个端口。``host`` / ``port`` 是普通类属性，服务什么有两种给法。

    **依赖即服务**——它直接依赖的 :class:`~canary_framework.asgi.App` 单元都在这个端口上，
    各自应答自己的 ``path``::

        class Gateway(Server):
            api = dep(LibraryApi)           # /
            metrics = dep(Metrics)          # /metrics

            port = 8010

    **显式赋值**——在 ``@init`` 里给 :attr:`app` 赋一个 ASGI 应用。赋了值就以它为准，依赖
    的应用单元不再自动加入，需要的话自己用 :func:`~canary_framework.asgi.dispatch` 拼::

        class Metrics(Server):
            port = 9100

            @init
            def build(self) -> None:
                self.app = make_asgi_app()

    - ``@start`` 绑定端口并开始服务。它依赖的单元此时都已启动。端口被占用时抛
      ``OSError``，已启动的依赖照常回收。
    - ``@stop`` 停止接收新连接，等在途请求结束。

    生命周期归 Canary，所以 ASGI 的 lifespan 是关闭的，信号也不由服务器接管：何时退出由
    进程入口决定。它不必是根单元——守护进程顺带开一个管理端口，就是多一条 ``dep()``。
    """

    #: 监听地址。
    host: str = "127.0.0.1"
    #: 监听端口。``0`` 由系统分配，开始服务后这里是实际端口。
    port: int = 8000
    #: 显式给出的 ASGI 应用。不赋值时服务直接依赖的应用单元。
    app: Application

    _uvicorn: _Uvicorn | None = None
    _serving: asyncio.Task[None] | None = None
    _socket: socket.socket | None = None

    def _application(self) -> Application:
        """What to serve: the app assigned explicitly, or the app units depended on directly.

        要服务的应用：显式赋值的那个，否则是直接依赖的应用单元按路径分发。
        """
        own: Application | None = getattr(self, "app", None)
        if own is not None:
            return own
        instances = scope_of(self).instances
        routes: dict[str, Application] = {}
        for cls in deps_of(type(self)):
            unit = instances[cls]
            if not isinstance(unit, App):
                continue
            if unit.path in routes:
                raise LifecycleError(
                    f"{type(self).__name__}: two apps answer {unit.path!r}. "
                    f"Give one of them a different path."
                )
            routes[unit.path] = unit.app
        if not routes:
            raise LifecycleError(
                f"{type(self).__name__}: nothing to serve. Depend on an App unit, "
                f"or assign self.app in an @init hook."
            )
        return dispatch(routes)

    @start
    async def _listen(self) -> None:
        app = self._application()
        # 自己绑定：交给 uvicorn 绑定的话，端口被占用时它直接 sys.exit，绕过失败回收。
        sock = self._socket = _bind(self.host, self.port)
        self.port = sock.getsockname()[1]
        server = self._uvicorn = _Uvicorn(uvicorn.Config(app, lifespan="off", log_config=None))
        serving = self._serving = asyncio.create_task(server.serve(sockets=[sock]))
        ready = asyncio.create_task(server.ready.wait())
        try:
            await asyncio.wait({serving, ready}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            ready.cancel()
        if serving.done():
            self._serving = None
            serving.result()
            raise RuntimeError(f"{type(self).__name__}: the server exited while starting")

    @stop
    async def _close(self) -> None:
        server, serving, sock = self._uvicorn, self._serving, self._socket
        self._uvicorn = self._serving = self._socket = None
        try:
            if server is not None and serving is not None:
                server.should_exit = True
                await serving
        finally:
            # 等待在途请求时被取消，套接字也要关掉。
            if sock is not None:
                sock.close()


class _Uvicorn(uvicorn.Server):
    """uvicorn 的服务器，加一个"已开始服务"的事件，并且不接管信号。"""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.ready = asyncio.Event()

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        self.ready.set()

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def _bind(host: str, port: int) -> socket.socket:
    """绑定一个监听套接字，协议显式写作 TCP。

    asyncio 只给协议号为 ``IPPROTO_TCP`` 的连接关闭 Nagle 算法，而连接的协议号继承自监听
    套接字。``socket.create_server`` 建出的套接字协议号是 0，于是每个连接都开着 Nagle：响应的
    头与体分两次写出，第二次要等对端的延迟确认，每个请求多出约 40 毫秒。
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    try:
        if os.name == "posix":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
    except BaseException:
        sock.close()
        raise
    return sock
