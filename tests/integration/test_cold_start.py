"""Integration — starting without a lifespan, and doing it exactly once.

没有 lifespan 时的冷启动：第一个请求把应用启起来。并发的首批请求必须排队等同一次启动，
而不是各自往下走。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import MutableMapping
from typing import Any

import pytest

from canary_framework import Canary, cocoa, on_init, on_start
from canary_framework.web import get, web_cocoa

pytestmark = pytest.mark.integration


def _http_scope() -> dict[str, Any]:
    return {
        "type": "http",
        "method": "GET",
        "path": "/ping",
        "headers": [],
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 1),
        "http_version": "1.1",
        "asgi": {"version": "3.0"},
    }


async def _call(app: Canary) -> object:
    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list[dict[str, Any]] = []

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(dict(message))

    await app(_http_scope(), receive, send)
    return sent[0]["status"]


async def test_concurrent_first_requests_all_get_served() -> None:
    """从前：第一个 200，其余全是 RuntimeError。

    启动过程只要让出过一次（连库、建池——现实里必然如此），后到的请求就会看见
    STARTING，于是跳过启动、直奔一个还没建好的服务入口。
    """
    started = 0

    @cocoa
    class Db:
        @on_start
        async def connect(self) -> None:
            nonlocal started
            started += 1
            await asyncio.sleep(0.01)  # 一次真实的让出

    @web_cocoa(deps=[Db])
    class Api:
        @get("/ping")
        async def ping(self) -> dict:
            return {"ok": True}

    app = Canary(Api)
    results = await asyncio.gather(*[_call(app) for _ in range(5)])

    assert results == [200] * 5
    assert started == 1  # 五个并发请求只启动一次


async def test_a_graph_without_web_units_says_so() -> None:
    """两种"没有服务入口"要分开说，而不是共用一句含糊的话。"""

    @cocoa
    class Plain:
        pass

    app = Canary(Plain)
    with pytest.raises(RuntimeError, match="no @web_cocoa unit is reachable"):
        await _call(app)


async def test_a_failed_startup_says_so() -> None:
    @web_cocoa
    class Api:
        @on_start
        async def boom(self) -> None:
            raise RuntimeError("cannot connect")

        @get("/ping")
        async def ping(self) -> dict:
            return {}

    app = Canary(Api)
    with pytest.raises(RuntimeError, match="cannot connect"):
        await _call(app)
    with pytest.raises(RuntimeError, match="startup failed"):
        await _call(app)  # 第二个请求要说清楚是启动失败过，而不是"没有服务入口"


async def test_the_probe_can_see_the_startup_phase(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """从前测不到：asyncio 在回调开始执行前就读过 debug 标志，而探针是在回调执行到
    一半（init 里）才打开的——整个启动期因此落在那个"还没开启"的回调里。
    """
    monkeypatch.setenv("CANARY_SLOW_CALLBACK_SECONDS", "0.05")

    @cocoa
    class Slow:
        @on_init
        def block(self) -> None:
            time.sleep(0.2)  # 装配期阻塞事件循环

    with caplog.at_level(logging.WARNING, logger="asyncio"):
        app = Canary(Slow)
        await app.init()
        await asyncio.sleep(0)  # 让出一次，asyncio 才会把上一个回调的耗时报出来
        await app.stop()

    blocked = [r for r in caplog.records if "took 0.2" in r.getMessage()]
    assert blocked, "启动期的阻塞应当被探针抓到"
