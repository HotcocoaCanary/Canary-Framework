"""Integration — lifecycle failures propagate and mark the runtime ``FAILED``."""

import pytest

from canary_framework import (
    Canary,
    LifecycleError,
    LifecycleState,
    cocoa,
    on_init,
    on_start,
    on_stop,
)

pytestmark = pytest.mark.integration


async def test_init_failure_propagates_and_marks_failed() -> None:
    @cocoa
    class Broken:
        @on_init
        def boom(self) -> None:
            raise RuntimeError("init exploded")

    canary = Canary(Broken)
    with pytest.raises(RuntimeError, match="init exploded"):
        await canary.init()

    assert canary.state is LifecycleState.FAILED
    # 失败态是不可逆的——后续 start 直接拒绝。
    with pytest.raises(LifecycleError):
        await canary.start()


async def test_start_failure_after_partial_start() -> None:
    started: list[str] = []

    @cocoa
    class First:
        @on_start
        def start(self) -> None:
            started.append("first")

    @cocoa(deps=[First])
    class Second:
        @on_start
        def start(self) -> None:
            started.append("second")
            raise RuntimeError("start exploded")

    canary = Canary(Second)
    await canary.init()
    with pytest.raises(RuntimeError, match="start exploded"):
        await canary.start()

    assert canary.state is LifecycleState.FAILED
    # 已启动的 First 保持启动；Second 在自身钩子内失败。
    assert started == ["first", "second"]


async def test_stop_failure_propagates_and_marks_failed() -> None:
    @cocoa
    class Broken:
        @on_stop
        def boom(self) -> None:
            raise RuntimeError("stop exploded")

    canary = Canary(Broken)
    await canary.init()
    await canary.start()

    with pytest.raises(RuntimeError, match="stop exploded"):
        await canary.stop()

    assert canary.state is LifecycleState.FAILED
