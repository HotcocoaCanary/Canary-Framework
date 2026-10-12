"""ASGI 服务器单元：监听是它的 @start，关闭是它的 @stop。"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import httpx
import pytest
import uvicorn

from canary_framework import Canary, LifecycleError, dep, init, start, stop
from canary_framework.asgi import Server
from canary_framework.test import running

pytestmark = pytest.mark.functional

events: list[str] = []

type _Message = MutableMapping[str, Any]


async def hello(
    scope: MutableMapping[str, Any],
    receive: Callable[[], Awaitable[_Message]],
    send: Callable[[_Message], Awaitable[None]],
) -> None:
    """一个不依赖任何框架的 ASGI 应用。"""
    body = f"hello {scope['path']}".encode()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": body})


class Database(Canary):
    @start
    def connect(self) -> None:
        events.append("db start")

    @stop
    def close(self) -> None:
        events.append("db stop")


class Hello(Server):
    database = dep(Database)

    port = 0

    @init
    def build(self) -> None:
        self.app = hello

    @start
    def announce(self) -> None:
        events.append("listening")


@pytest.fixture(autouse=True)
def _clear() -> None:
    events.clear()


def _url(server: Server, path: str = "/") -> str:
    return f"http://{server.host}:{server.port}{path}"


async def test_it_serves_any_asgi_app_over_a_real_socket() -> None:
    async with running(Hello) as server, httpx.AsyncClient() as client:
        assert server.port != 0
        assert (await client.get(_url(server, "/there"))).text == "hello /there"


async def test_connections_have_nagle_off() -> None:
    """响应的头与体分两次写出；Nagle 开着时第二次要等对端的延迟确认，每个请求多约 40 毫秒。

    asyncio 只给协议号为 TCP 的连接关 Nagle，而协议号继承自监听套接字——所以这里看的是
    服务端那一侧已接受的连接。
    """
    async with running(Hello) as server, httpx.AsyncClient() as client:
        await client.get(_url(server))
        assert server._uvicorn is not None
        (connection,) = server._uvicorn.server_state.connections
        accepted = connection.transport.get_extra_info("socket")
        assert accepted.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)


async def test_a_cancelled_stop_still_closes_the_socket() -> None:
    """``stop()`` 等在途请求结束；等待被取消时，监听套接字也要关掉。"""

    class Stuck(Server):
        port = 0

        @init
        def build(self) -> None:
            async def never(scope: Any, receive: Any, send: Any) -> None:
                await asyncio.Event().wait()

            self.app = never

    server = Stuck()
    await server.init()
    await server.start()
    listening = server._socket
    assert listening is not None
    async with httpx.AsyncClient() as client:
        request = asyncio.create_task(client.get(_url(server)))
        await asyncio.sleep(0.05)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(server.stop(), 0.3)
        request.cancel()
    assert listening.fileno() == -1


async def test_class_parameters_go_to_uvicorn_and_bound_the_wait_for_requests() -> None:
    """不设 ``timeout_graceful_shutdown`` 时 ``stop()`` 一直等在途请求；设了就有上限。"""

    class Stuck(Server, timeout_graceful_shutdown=1):
        port = 0

        @init
        def build(self) -> None:
            async def never(scope: Any, receive: Any, send: Any) -> None:
                await asyncio.Event().wait()

            self.app = never

    server = Stuck()
    await server.init()
    await server.start()
    assert server._uvicorn is not None
    assert server._uvicorn.config.timeout_graceful_shutdown == 1
    async with httpx.AsyncClient() as client:
        request = asyncio.create_task(client.get(_url(server)))
        await asyncio.sleep(0.05)
        await asyncio.wait_for(server.stop(), 5)
        # uvicorn 取消了那个请求的任务，对端得到 500 而不是一直挂着。
        assert (await request).status_code == 500


def test_a_subclass_inherits_class_parameters_and_overrides_its_own() -> None:
    class Base(Server, timeout_keep_alive=1, backlog=16): ...

    class Tuned(Base, backlog=32): ...

    assert Server.__canary_server__ == {}
    assert Base.__canary_server__ == {"timeout_keep_alive": 1, "backlog": 16}
    assert Tuned.__canary_server__ == {"timeout_keep_alive": 1, "backlog": 32}


@pytest.mark.parametrize("option", ["app", "host", "port", "lifespan", "workers", "reload"])
def test_options_that_belong_elsewhere_are_refused(option: str) -> None:
    with pytest.raises(TypeError, match=f"{option} cannot be passed to uvicorn here"):
        type("Wrong", (Server,), {}, **{option: 1})


async def test_dependencies_start_before_it_listens_and_stop_after_it_closes() -> None:
    async with running(Hello) as server:
        url = _url(server)
        assert events == ["db start", "listening"]
    assert events == ["db start", "listening", "db stop"]
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectError):
            await client.get(url)


async def test_a_port_in_use_fails_the_start_and_reclaims_what_started() -> None:
    with socket.create_server(("127.0.0.1", 0)) as taken:

        class Busy(Hello):
            port = taken.getsockname()[1]

        with pytest.raises(OSError, match="in use"):
            async with Busy():
                raise AssertionError("unreachable")
    assert events == ["db start", "db stop"]


async def test_it_can_be_restarted() -> None:
    server = Hello()
    for _ in range(2):
        async with server, httpx.AsyncClient() as client:
            assert (await client.get(_url(server))).text == "hello /"


async def test_it_need_not_be_the_root() -> None:
    class Daemon(Canary):
        admin = dep(Hello)

    async with running(Daemon) as daemon, httpx.AsyncClient() as client:
        assert (await client.get(_url(daemon.admin))).status_code == 200


async def test_it_listens_on_ipv6_when_the_host_is_one() -> None:
    if not socket.has_ipv6:
        pytest.skip("no IPv6 on this machine")

    class Six(Hello):
        host = "::1"

    try:
        async with running(Six) as server, httpx.AsyncClient() as client:
            assert (await client.get(f"http://[::1]:{server.port}/")).status_code == 200
    except OSError:
        pytest.skip("IPv6 loopback is not available")


async def test_with_nothing_to_serve_the_start_fails_and_says_what_to_do() -> None:
    class Empty(Server):
        database = dep(Database)
        port = 0

    with pytest.raises(LifecycleError, match=r"Depend on an App unit, or assign self\.app"):
        async with Empty():
            raise AssertionError("unreachable")
    assert events == ["db start", "db stop"]


async def test_stop_without_start_is_a_no_op() -> None:
    server = Hello()
    await server.init()
    await server.stop()
    assert events == []


async def test_a_server_that_exits_while_starting_fails_the_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exits_early(self: uvicorn.Server, sockets: object = None) -> None:
        return None

    monkeypatch.setattr(uvicorn.Server, "serve", exits_early)
    with pytest.raises(RuntimeError, match="exited while starting"):
        async with Hello():
            raise AssertionError("unreachable")
    assert events == ["db start", "db stop"]


async def test_a_crash_while_starting_is_raised_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    async def crashes(self: uvicorn.Server, sockets: object = None) -> None:
        raise ValueError("bad config")

    monkeypatch.setattr(uvicorn.Server, "serve", crashes)
    with pytest.raises(ValueError, match="bad config"):
        async with Hello():
            raise AssertionError("unreachable")
    assert events == ["db start", "db stop"]
