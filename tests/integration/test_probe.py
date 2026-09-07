"""Integration — the opt-in event-loop latency probe.

拒绝同步 handler 是声明期检查，只看得见签名；这条是运行期检查，抓的是实际发生的
阻塞。它改动的是整个事件循环的全局状态，所以必须还原。
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from canary_framework import Canary, LifecycleError, cocoa

pytestmark = pytest.mark.integration


@cocoa
class Bare:
    pass


async def test_the_probe_is_off_by_default() -> None:
    loop = asyncio.get_running_loop()
    before = (loop.get_debug(), loop.slow_callback_duration)

    async with Canary(Bare):
        assert (loop.get_debug(), loop.slow_callback_duration) == before


async def test_the_probe_is_restored_on_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """全局状态改了就要还原——否则一个开了探针的应用会污染同进程后续所有代码。"""
    monkeypatch.setenv("CANARY_SLOW_CALLBACK_SECONDS", "0.05")
    loop = asyncio.get_running_loop()
    before = (loop.get_debug(), loop.slow_callback_duration)

    async with Canary(Bare):
        assert loop.get_debug()
        assert loop.slow_callback_duration == pytest.approx(0.05)

    assert (loop.get_debug(), loop.slow_callback_duration) == before


async def test_the_probe_catches_blocking_inside_an_async_body(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """签名是 async、函数体是同步——签名检查看不见的那种阻塞。"""
    import time

    monkeypatch.setenv("CANARY_SLOW_CALLBACK_SECONDS", "0.02")

    @cocoa
    class Blocks:
        pass

    with caplog.at_level(logging.WARNING, logger="asyncio"):
        async with Canary(Blocks):
            # 让出一次：asyncio 在每个 handle 开始前才决定要不要计时，所以阻塞必须
            # 发生在开启探针之后的下一个 handle 里。
            await asyncio.sleep(0)
            time.sleep(0.05)  # async 上下文里的同步阻塞
            await asyncio.sleep(0)  # 结束这个 handle，让循环记账

    assert any("took" in record.getMessage() for record in caplog.records)


async def test_a_malformed_probe_setting_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CANARY_SLOW_CALLBACK_SECONDS", "very slow")
    with pytest.raises(LifecycleError, match="number of seconds"):
        await Canary(Bare).init()
