"""Integration — the two host protocols that exist in Python, and nothing else.

各领域的宿主只有两种形状：收一个异步上下文管理器（ASGI 的 lifespan、MCP、FastStream），
或者收成对的启动/关停回调（Quart、Sanic、arq、Dramatiq）。这里用标准库把两种都模拟出来
——框架零依赖，测试不该为了验证协议就装一个 web 框架。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

import pytest

from canary_framework import Canary, cocoa, on_start, on_stop

pytestmark = pytest.mark.integration


@cocoa
class Db:
    @on_start
    async def up(self) -> None:
        await asyncio.sleep(0)  # 一次真实的让出
        self.events.append("start")

    @on_stop
    async def down(self) -> None:
        self.events.append("stop")

    def __init__(self) -> None:
        self.events: list[str] = []


async def test_lifespan_yields_none_not_the_container() -> None:
    """这一条就是那个 bug 的本体。

    ASGI 的 lifespan 协议把交出来的值当作要合并进 ``scope["state"]`` 的映射。交出容器
    自己会让宿主去 ``dict.update(canary)``，漏出一个毫无线索的 ``KeyError: 0``。
    """
    canary = Canary(Db)
    async with canary.lifespan() as yielded:
        assert yielded is None
        assert canary.state.name == "STARTED"
    assert canary[Db].events == ["start", "stop"]


async def test_the_asgi_dialect_that_used_to_break() -> None:
    """把 Starlette 对交出值做的事原样模拟一遍：合并进一个 state 字典。"""
    canary = Canary(Db)
    state: dict[str, Any] = {}

    async with canary.lifespan(object()) as maybe_state:  # 宿主会把自己传进来
        if maybe_state is not None:
            state.update(maybe_state)  # ← 从前在这里炸
    assert state == {}
    assert canary[Db].events == ["start", "stop"]


async def test_lifespan_takes_the_host_or_nothing() -> None:
    """宿主协议是 ``Callable[[Host], AsyncContextManager]``；没有宿主时也要能直接用。"""
    for arg in ((), ("some host object",)):
        canary = Canary(Db)
        async with canary.lifespan(*arg):
            assert canary.state.name == "STARTED"
        assert canary[Db].events == ["start", "stop"]


async def test_a_host_that_takes_a_context_manager_factory() -> None:
    """形状一：宿主收一个 ``Callable[[Host], AsyncContextManager]``（ASGI / MCP / FastStream）。"""

    async def host(make_lifespan: Callable[[Any], Any]) -> str:
        async with make_lifespan(host):
            return "served"

    canary = Canary(Db)
    assert await host(canary.lifespan) == "served"
    assert canary[Db].events == ["start", "stop"]


async def test_a_host_that_takes_paired_callbacks() -> None:
    """形状二：宿主收成对回调（Quart、Sanic、arq、Dramatiq）—— 用三个显式方法。"""
    canary = Canary(Db)
    on_startup: list[Callable[[], Any]] = [canary.start]
    on_shutdown: list[Callable[[], Any]] = [canary.stop]

    for hook in on_startup:
        await hook()
    assert canary.state.name == "STARTED"
    for hook in on_shutdown:
        await hook()
    assert canary[Db].events == ["start", "stop"]


async def test_it_composes_with_async_exit_stack() -> None:
    """``AsyncExitStack`` 是标准库对"一堆有生命期的东西"的通用管理方式。"""
    canary = Canary(Db)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(canary.lifespan())
        assert canary.state.name == "STARTED"
    assert canary[Db].events == ["start", "stop"]


async def test_lifespan_nests_inside_another_lifespan() -> None:
    """宿主常常把若干个 lifespan 串起来，我们要能当其中一环。"""
    canary = Canary(Db)
    order: list[str] = []

    @asynccontextmanager
    async def outer() -> AsyncIterator[None]:
        order.append("outer-in")
        async with canary.lifespan():
            yield
        order.append("outer-out")

    async with outer():
        order.append("serving")
    assert order == ["outer-in", "serving", "outer-out"]
    assert canary[Db].events == ["start", "stop"]


async def test_a_failed_startup_reaches_the_host() -> None:
    """宿主靠异常判断启动失败；它必须原样穿过 lifespan。"""

    @cocoa
    class Boom:
        @on_start
        async def up(self) -> None:
            raise RuntimeError("下游连不上")

    canary = Canary(Boom)
    with pytest.raises(RuntimeError, match="下游连不上"):
        async with canary.lifespan():
            pass
    # 很多宿主随后会无条件调一次关停，不能二次爆炸
    await canary.stop()
    assert canary.state.name == "FAILED"


async def test_async_with_canary_still_hands_back_the_container() -> None:
    """``async with canary`` 服务的是你自己的代码，它交出容器——这条不能被上面那条改掉。"""
    canary = Canary(Db)
    async with canary as got:
        assert got is canary
