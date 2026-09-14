"""回收：逆序、单个失败不中断、幂等。"""

from __future__ import annotations

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
