"""进入：依赖序、只跑一次、环、并发、失败。"""

from __future__ import annotations

import asyncio
import time

import pytest

from canary_framework import (
    Canary,
    CircularDependencyError,
    LifecycleError,
    dep,
    enter,
    init,
    scope_of,
    start,
)

pytestmark = pytest.mark.integration


async def test_dependencies_run_before_the_unit_that_declares_them() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @init
        def go(self) -> None:
            seen.append("leaf")

    class Middle(Canary):
        leaf = dep(Leaf)

        @init
        def go(self) -> None:
            seen.append("middle")

    class Root(Canary):
        middle = dep(Middle)

        @init
        def go(self) -> None:
            seen.append("root")

    await enter(Root(), init)
    assert seen == ["leaf", "middle", "root"]


async def test_a_shared_dependency_enters_exactly_once() -> None:
    seen: list[str] = []

    class Shared(Canary):
        @init
        def go(self) -> None:
            seen.append("shared")

    class Left(Canary):
        shared = dep(Shared)

    class Right(Canary):
        shared = dep(Shared)

    class Root(Canary):
        left = dep(Left)
        right = dep(Right)

    await enter(Root(), init)
    assert seen == ["shared"]


async def test_advancing_the_same_phase_twice_is_a_no_op() -> None:
    seen: list[str] = []

    class Once(Canary):
        @init
        def go(self) -> None:
            seen.append("once")

    unit = Once()
    await enter(unit, init)
    await enter(unit, init)
    assert seen == ["once"]


async def test_a_cycle_reports_the_path_it_actually_walked() -> None:
    class A(Canary): ...

    class B(Canary):
        a = dep(A)

    A.b = dep(B)  # type: ignore[attr-defined]  # 环只能这样事后接上：dep(B) 在类体里求值时 B 还不存在

    with pytest.raises(CircularDependencyError) as caught:
        await enter(A(), init)

    assert [t.__name__ for t in caught.value.cycle] == ["A", "B", "A"]


async def test_independent_dependencies_enter_concurrently() -> None:
    class SlowLeft(Canary):
        @start
        async def go(self) -> None:
            await asyncio.sleep(0.05)

    class SlowRight(Canary):
        @start
        async def go(self) -> None:
            await asyncio.sleep(0.05)

    class Root(Canary):
        left = dep(SlowLeft)
        right = dep(SlowRight)

    root = Root()
    await enter(root, init)
    began = time.perf_counter()
    await enter(root, start)
    elapsed = time.perf_counter() - began

    assert elapsed < 0.09  # 顺序执行要 0.1s


async def test_one_failing_sibling_surfaces_as_itself_not_as_a_group() -> None:
    class Boom(Canary):
        @init
        def go(self) -> None:
            raise RuntimeError("boom")

    class Fine(Canary):
        @init
        async def go(self) -> None:
            await asyncio.sleep(0.02)

    class Root(Canary):
        boom = dep(Boom)
        fine = dep(Fine)

    with pytest.raises(RuntimeError, match="boom"):
        await enter(Root(), init)


async def test_a_phase_refuses_to_run_before_its_declared_predecessor() -> None:
    class Unit(Canary):
        @start
        def go(self) -> None: ...

    with pytest.raises(LifecycleError, match="@init has not run"):
        await enter(Unit(), start)


async def test_the_ledger_is_always_a_valid_topological_order() -> None:
    class Config(Canary): ...

    class Database(Canary):
        config = dep(Config)

    class Cache(Canary):
        config = dep(Config)

    class Root(Canary):
        database = dep(Database)
        cache = dep(Cache)

    root = Root()
    await enter(root, init)
    await enter(root, start)

    order = [type(unit) for unit in scope_of(root).entered(start).values()]
    assert order.index(Config) < order.index(Database)
    assert order.index(Config) < order.index(Cache)
    assert order.index(Database) < order.index(Root)
    assert order.index(Cache) < order.index(Root)


async def test_two_simultaneous_failures_are_reported_together() -> None:
    gate = asyncio.Barrier(2)

    class Left(Canary):
        @init
        async def go(self) -> None:
            await gate.wait()
            raise RuntimeError("left")

    class Right(Canary):
        @init
        async def go(self) -> None:
            await gate.wait()
            raise RuntimeError("right")

    class Root(Canary):
        left = dep(Left)
        right = dep(Right)

    with pytest.raises(ExceptionGroup) as caught:
        await enter(Root(), init)

    assert {str(exc) for exc in caught.value.exceptions} == {"left", "right"}


@pytest.mark.slow
async def test_a_deep_dependency_chain_does_not_hit_the_recursion_limit() -> None:
    unit: type[Canary] = type("L0", (Canary,), {})
    for i in range(1, 5000):
        unit = type(f"L{i}", (Canary,), {"below": dep(unit)})

    root = unit()
    await root.init()
    assert len(scope_of(root).instances) == 5000


async def test_a_failing_dependency_reached_by_two_paths_runs_once() -> None:
    runs: list[str] = []

    class Flaky(Canary):
        @start
        def connect(self) -> None:
            runs.append("flaky")
            raise RuntimeError("boom")

    class Middle(Canary):
        flaky = dep(Flaky)

    class Root(Canary):
        flaky = dep(Flaky)
        middle = dep(Middle)

    root = Root()
    await enter(root, init)
    with pytest.raises(RuntimeError, match="boom"):
        await enter(root, start)
    assert runs == ["flaky"]

    # 进入结束后失败记录被清除，因此可以重试
    with pytest.raises(RuntimeError, match="boom"):
        await enter(root, start)
    assert runs == ["flaky", "flaky"]
