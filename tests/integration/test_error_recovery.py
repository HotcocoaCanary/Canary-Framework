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


async def test_an_on_init_failure_propagates_and_marks_failed() -> None:
    """``@on_init`` 阶段失败时台账还是空的，所以回滚是空转——不需要为它单写一条规则。"""

    @cocoa
    class Broken:
        @on_init
        def boom(self) -> None:
            raise RuntimeError("init exploded")

    canary = Canary(Broken)
    with pytest.raises(RuntimeError, match="init exploded"):
        await canary.start()

    assert canary.state is LifecycleState.FAILED
    # 失败态是不可逆的——后续 start 直接拒绝。
    with pytest.raises(LifecycleError):
        await canary.start()


async def test_start_failure_rolls_back_everything_started() -> None:
    """启动失败时回滚：要么全部启动，要么什么都没启动。"""
    log: list[str] = []

    @cocoa
    class First:
        @on_start
        def start(self) -> None:
            log.append("first.start")

        @on_stop
        def stop(self) -> None:
            log.append("first.stop")

    @cocoa(deps=[First])
    class Second:
        @on_start
        def start(self) -> None:
            log.append("second.start")
            raise RuntimeError("start exploded")

        @on_stop
        def stop(self) -> None:
            log.append("second.stop")

    canary = Canary(Second)
    with pytest.raises(RuntimeError, match="start exploded"):
        await canary.start()

    assert canary.state is LifecycleState.FAILED
    # 回收含失败单元自身（它可能已经拿到了一半资源），且严格逆序。
    assert log == ["first.start", "second.start", "second.stop", "first.stop"]


async def test_stop_is_legal_and_idempotent_from_failed() -> None:
    """``stop()`` 是唯一的回收路径，正常结束与失败结束共用它。"""

    @cocoa
    class Broken:
        @on_start
        def start(self) -> None:
            raise RuntimeError("start exploded")

    canary = Canary(Broken)
    with pytest.raises(RuntimeError):
        await canary.start()

    # 从 FAILED 调用合法；台账已在回滚时清空，这里是空转，且不抹掉失败态。
    await canary.stop()
    await canary.stop()
    assert canary.state is LifecycleState.FAILED


async def test_stop_failure_does_not_abort_the_remaining_units() -> None:
    """单个 ``@on_stop`` 抛出不中断回收；异常收集后合并为 ``ExceptionGroup``。"""
    log: list[str] = []

    @cocoa
    class Innermost:
        @on_stop
        def stop(self) -> None:
            log.append("innermost.stop")

    @cocoa(deps=[Innermost])
    class Broken:
        @on_stop
        def boom(self) -> None:
            log.append("broken.stop")
            raise RuntimeError("stop exploded")

    @cocoa(deps=[Broken])
    class Outermost:
        @on_stop
        def stop(self) -> None:
            log.append("outermost.stop")

    canary = Canary(Outermost)
    await canary.start()

    with pytest.raises(ExceptionGroup) as caught:
        await canary.stop()

    assert [type(exc) for exc in caught.value.exceptions] == [RuntimeError]
    # 最内层的资源仍然被回收——这是本条修复的全部意义。
    assert log == ["outermost.stop", "broken.stop", "innermost.stop"]
    assert canary.state is LifecycleState.FAILED
