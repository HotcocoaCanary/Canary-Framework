"""The server unit.

服务器单元：监听端口是它的 ``@start``，关闭是它的 ``@stop``。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import socket
from collections.abc import Iterator, Mapping
from typing import Any, ClassVar

import uvicorn

from canary_framework.core import Canary, LifecycleError, deps_of, scope_of, start, stop
from canary_framework.web.asgi import Application, dispatch

#: 不能当作类参数传给 uvicorn 的选项：它们在这里另有归属。
_OWNED = frozenset({"app", "host", "port", "uds", "fd", "reload", "workers"})


class Server(Canary):
    """A unit that listens on one port and serves the ASGI applications it is given.

    服务器单元：监听一个端口。``host`` / ``port`` 是普通类属性，服务什么有两种给法。

    **依赖即服务**——它直接依赖的单元里，可调用并且声明了 ``path`` 的就是应用，各自在这个
    端口上应答自己的 ``path``。两个条件缺一不可：恰好可调用的普通协作者不会被当成应用::

        class Gateway(Server):
            api = dep(LibraryApi)           # LibraryApi.path = "/"
            metrics = dep(Metrics)          # Metrics.path = "/metrics"

            port = 8010

    **显式赋值**——在 ``@init`` 里给 :attr:`app` 赋任何一个 ASGI 应用，比如一个 FastAPI 对象。
    赋了值就以它为准，依赖的应用单元不再自动加入，需要的话自己用
    :func:`~canary_framework.web.asgi.dispatch` 拼::

        class Gateway(Server):
            port = 8010

            @init
            def build(self) -> None:
                self.app = fastapi_app

    - ``@start`` 绑定端口并开始服务。它依赖的单元此时都已启动。端口被占用时抛
      ``OSError``，已启动的依赖照常回收。
    - ``@stop`` 停止接收新连接，等在途请求结束。

    类参数原样传给 ``uvicorn.Config``，子类继承父类的全部类参数，只覆盖自己写出的那些::

        class Gateway(Server, timeout_graceful_shutdown=10, proxy_headers=True):
            api = dep(LibraryApi)

    ``timeout_graceful_shutdown`` 值得设：不设时 ``@stop`` 会一直等到在途请求全部结束，一个
    不结束的长连接就能让停机卡住，排在它后面的依赖也得不到回收。

    生命周期归 Canary，所以默认不向应用发 ASGI 的 lifespan 消息，信号也不由它接管：何时退出
    由进程入口决定。被服务的应用若把初始化写在自己的 lifespan 里（别的框架的应用常常如此），
    用 ``lifespan="on"`` 打开：应用的启动发生在本单元的 ``@start`` 里、监听之前，回收发生在
    ``@stop`` 里。本框架的应用单元此时已由 Canary 启动，只会应答，不会被重复驱动。

    它不必是根单元——守护进程顺带开一个管理端口，就是多一条 ``dep()``。

    :param options: 原样传给 ``uvicorn.Config(...)`` 的参数（``timeout_graceful_shutdown``、
        ``timeout_keep_alive``、``proxy_headers``、``ssl_certfile`` ……）。
    :raises TypeError: 传了在这里另有归属的选项：地址是 ``host`` / ``port`` 属性，应用是它
        依赖的单元，重载与多进程不归 uvicorn 管。
    """

    #: 监听地址。
    host: str = "127.0.0.1"
    #: 监听端口。``0`` 由系统分配，服务期间这里是实际端口，停止后还原成声明的值。
    port: int = 8000
    #: 显式给出的 ASGI 应用。不赋值时服务直接依赖的应用单元。
    app: Application

    #: 本类的类参数，原样传给 ``uvicorn.Config``。
    __canary_server__: ClassVar[Mapping[str, Any]] = {}

    _uvicorn: _Uvicorn | None = None
    _serving: asyncio.Task[None] | None = None
    _socket: socket.socket | None = None
    _declared: int | None = None

    def __init_subclass__(cls, **options: Any) -> None:
        super().__init_subclass__()
        owned = sorted(_OWNED & options.keys())
        if owned:
            raise TypeError(
                f"{cls.__name__}: {', '.join(owned)} cannot be passed to uvicorn here. "
                f"The address is the host / port attributes, the application is what the "
                f"server depends on, and the lifecycle belongs to Canary."
            )
        cls.__canary_server__ = {**cls.__canary_server__, **options}

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
            unit: Any = instances[cls]
            path = getattr(unit, "path", None)
            if path is None or not callable(unit):
                continue  # 不是应用：应用要可调用，并且声明了 path
            if path in routes:
                raise LifecycleError(
                    f"{type(self).__name__}: two apps answer {path!r}. "
                    f"Give one of them a different path."
                )
            routes[path] = unit
        if not routes:
            raise LifecycleError(
                f"{type(self).__name__}: nothing to serve. Depend on an application unit "
                f"(callable, with a path attribute), "
                f"or assign self.app in an @init hook."
            )
        return dispatch(routes)

    @start
    async def _listen(self) -> None:
        app = self._application()
        # 自己绑定：交给 uvicorn 绑定的话，端口被占用时它直接 sys.exit，绕过失败回收。
        sock = self._socket = _bind(self.host, self.port)
        self._declared = self.port
        self.port = sock.getsockname()[1]
        options = {"log_config": None, "lifespan": "off", **self.__canary_server__}
        server = self._uvicorn = _Uvicorn(uvicorn.Config(app, **options))
        serving = self._serving = asyncio.create_task(server.serve(sockets=[sock]))
        ready = asyncio.create_task(server.ready.wait())
        try:
            await asyncio.wait({serving, ready}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            ready.cancel()
        if serving.done():
            # 没能开始服务：把绑定的端口还回去，再报告原因。
            self._uvicorn = self._serving = self._socket = None
            self.port, self._declared = self._declared, None
            sock.close()
            serving.result()
            raise RuntimeError(f"{type(self).__name__}: the server exited while starting")

    @stop
    async def _close(self) -> None:
        server, serving, sock = self._uvicorn, self._serving, self._socket
        self._uvicorn = self._serving = self._socket = None
        if self._declared is not None:
            # 还原声明的端口：否则 ``port = 0`` 的服务器重启时会去绑上次分到的那个。
            self.port, self._declared = self._declared, None
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
        try:
            await super().startup(sockets=sockets)
        except SystemExit:
            # 应用的 lifespan 启动失败时 uvicorn 直接 sys.exit，那会绕过失败回收。
            raise RuntimeError(
                "the application's lifespan failed during startup; "
                "the uvicorn.error logger has the traceback"
            ) from None
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
