"""Integration — lifespan failures must reach the caller, not hang it.

ASGI 调用方靠 lifespan 任务抛异常来传播失败。只汇报不抛，调用方会以为启动成功，
挂起就从 startup 搬到了 shutdown——这类问题只在完整实现了 lifespan 协议的调用方
身上暴露，用 ASGI transport 或直接驱动 ``_lifespan`` 都测不到，所以这里用 TestClient。
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest
from starlette.testclient import TestClient

from canary_framework import Canary, cocoa, on_start, on_stop

pytestmark = pytest.mark.integration


def _finishes_within(target: Callable[[], None], seconds: float = 5.0) -> bool:
    """Run *target* in a thread; ``False`` means it hung (so this test never hangs)."""
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=seconds)
    return not thread.is_alive()


@cocoa
class FailsToStart:
    @on_start
    async def boom(self) -> None:
        raise RuntimeError("startup exploded")


@cocoa
class FailsToStop:
    @on_stop
    async def boom(self) -> None:
        raise RuntimeError("shutdown exploded")


def test_a_startup_failure_reaches_the_caller() -> None:
    with pytest.raises(RuntimeError, match="startup exploded"), TestClient(Canary(FailsToStart)):
        pass


def test_a_startup_failure_does_not_hang_the_caller() -> None:
    """回归：只 return 会让 __enter__ 成功、__exit__ 永久挂起。"""

    def drive() -> None:
        with pytest.raises(RuntimeError), TestClient(Canary(FailsToStart)):
            pass

    assert _finishes_within(drive), "TestClient hung instead of reporting the failure"


def test_a_shutdown_failure_reaches_the_caller() -> None:
    """关停失败不该被 shutdown.complete 掩盖。"""
    with pytest.raises(ExceptionGroup), TestClient(Canary(FailsToStop)):
        pass
