"""回收：逆序、单个失败不中断、幂等、等待进行中的推进。"""

from __future__ import annotations

import asyncio

import pytest

from canary_framework import Canary, advance, dep, init, scope_of, start, stop, unwind

pytestmark = pytest.mark.integration


async def test_units_are_reclaimed_in_reverse_order() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @stop
        def go(self) -> None:
            seen.append("leaf")

    class Middle(Canary):
        leaf = dep(Leaf)

        @stop
        def go(self) -> None:
            seen.append("middle")

    class Root(Canary):
        middle = dep(Middle)

        @stop
        def go(self) -> None:
            seen.append("root")

    root = Root()
    await advance(root, init)
    await advance(root, start)
    await root.stop()

    assert seen == ["root", "middle", "leaf"]


async def test_one_failing_stop_does_not_abort_the_rest() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @stop
        def go(self) -> None:
            seen.append("leaf")

    class Angry(Canary):
        leaf = dep(Leaf)

        @stop
        def go(self) -> None:
            raise RuntimeError("cannot close")

    class Root(Canary):
        angry = dep(Angry)

        @stop
        def go(self) -> None:
            seen.append("root")

    root = Root()
    await advance(root, init)
    await advance(root, start)

    with pytest.raises(ExceptionGroup) as caught:
        await root.stop()

    assert seen == ["root", "leaf"]  # 出错的那个中间单元没挡住两边
    assert len(caught.value.exceptions) == 1
    assert "raised by Angry.go" in (caught.value.exceptions[0].__notes__ or [""])[0]


async def test_reclaiming_twice_is_idempotent() -> None:
    seen: list[str] = []

    class Unit(Canary):
        @stop
        def go(self) -> None:
            seen.append("stop")

    unit = Unit()
    await advance(unit, init)
    await advance(unit, start)
    await unit.stop()
    await unit.stop()

    assert seen == ["stop"]


async def test_reclaiming_something_that_never_started_is_a_no_op() -> None:
    class Unit(Canary):
        @stop
        def go(self) -> None:
            raise AssertionError("must not run")

    await Unit().stop()


async def test_unwind_reclaims_whatever_entered_the_named_phase() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @init
        def prepare(self) -> None: ...

        @stop
        def go(self) -> None:
            seen.append("leaf")

    class Root(Canary):
        leaf = dep(Leaf)

        @stop
        def go(self) -> None:
            seen.append("root")

    root = Root()
    await advance(root, init)

    # 只推进过 init，所以按 init 的台账回收；start 的台账是空的。
    assert await unwind(scope_of(root), stop, undoing=start) == []
    assert await unwind(scope_of(root), stop, undoing=init) == []
    assert seen == ["root", "leaf"]


async def test_stop_waits_for_an_in_flight_start_before_reclaiming() -> None:
    seen: list[str] = []
    entered = asyncio.Event()

    class Slow(Canary):
        @start
        async def connect(self) -> None:
            seen.append("start begin")
            entered.set()
            await asyncio.sleep(0.01)
            seen.append("start end")

        @stop
        async def close(self) -> None:
            seen.append("stop")

    class Root(Canary):
        slow = dep(Slow)

    root = Root()
    await root.init()
    starting = asyncio.create_task(root.start())
    await entered.wait()
    await root.stop()
    await starting

    assert seen == ["start begin", "start end", "stop"]


async def test_stop_reclaims_an_in_flight_start_that_fails() -> None:
    seen: list[str] = []
    entered = asyncio.Event()

    class Flaky(Canary):
        @start
        async def connect(self) -> None:
            entered.set()
            await asyncio.sleep(0.01)
            raise RuntimeError("boom")

        @stop
        async def close(self) -> None:
            seen.append("stop")

    class Root(Canary):
        flaky = dep(Flaky)

    root = Root()
    await root.init()
    starting = asyncio.create_task(root.start())
    await entered.wait()
    await root.stop()

    with pytest.raises(RuntimeError, match="boom"):
        await starting
    assert seen == ["stop"]


async def test_stop_waits_for_the_whole_chain_still_advancing() -> None:
    seen: list[str] = []
    entered = asyncio.Event()

    class Leaf(Canary):
        @start
        async def connect(self) -> None:
            entered.set()
            await asyncio.sleep(0.01)

        @stop
        def close(self) -> None:
            seen.append("leaf")

    class Middle(Canary):
        leaf = dep(Leaf)

        @stop
        def close(self) -> None:
            seen.append("middle")

    class Root(Canary):
        middle = dep(Middle)

        @stop
        def close(self) -> None:
            seen.append("root")

    root = Root()
    await root.init()
    starting = asyncio.create_task(root.start())
    await entered.wait()
    await root.stop()
    await starting

    assert seen == ["root", "middle", "leaf"]
