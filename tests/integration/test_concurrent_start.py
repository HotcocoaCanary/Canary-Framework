"""Integration — starting independent units concurrently, and failing safely while doing it.

并发启动：互不依赖的单元同时起。最容易写错的不是并发本身，是**并发下的失败路径**——
谁被取消、谁进了台账、逆序回收还对不对。
"""

from __future__ import annotations

import asyncio
import time

import pytest

from canary_framework import Canary, cocoa, on_init, on_start, on_stop

pytestmark = pytest.mark.integration


def slow(
    name: str, ms: float, deps: list[type] | None = None, log: list[str] | None = None
) -> type:
    """一个启动要花 ms 毫秒的单元。"""

    async def boot(self: object, n: str = name, d: float = ms / 1000) -> None:
        await asyncio.sleep(d)
        if log is not None:
            log.append(n)

    return cocoa(deps=deps or [])(type(name, (), {"boot": on_start(boot)}))


async def test_independent_units_start_together() -> None:
    """三个互不依赖、各 60ms 的单元：顺序要 180ms，并发只要一个的时间。"""
    root_seq = _three_branches()
    began = time.perf_counter()
    async with Canary(root_seq):
        pass
    sequential_ms = (time.perf_counter() - began) * 1e3

    began = time.perf_counter()
    async with Canary(_three_branches(), start_concurrency=3):
        pass
    concurrent_ms = (time.perf_counter() - began) * 1e3

    assert sequential_ms > 150  # 三个 60ms 排队
    assert concurrent_ms < 120  # 并发之后贴着单个的耗时
    assert sequential_ms / concurrent_ms > 1.8


def _three_branches() -> type:
    config = cocoa(type("Config", (), {}))
    leaves = [slow(f"IO{i}", 60, [config]) for i in range(3)]
    return cocoa(deps=leaves)(type("App", (), {}))


async def test_dependencies_are_still_honoured() -> None:
    """并发不能越过依赖：一个单元只在它的依赖**全部跑完**之后才开始。"""
    log: list[str] = []
    first = slow("First", 40, log=log)
    second = slow("Second", 5, [first], log=log)
    other = slow("Other", 60, log=log)
    root = cocoa(deps=[second, other])(type("App", (), {}))

    async with Canary(root, start_concurrency=4):
        pass

    assert log.index("First") < log.index("Second")
    # Other 和 First 无关，它比 First+Second 都慢，所以最后完成——说明确实是并行的
    assert log[-1] == "Other"


async def test_the_init_barrier_holds_under_concurrency() -> None:
    """两轮之间是硬同步点：整张图各就各位，才允许任何单元开工。"""
    log: list[str] = []

    def phased(name: str, init_ms: float, deps: list[type] | None = None) -> type:
        async def prepare(self: object, n: str = name, d: float = init_ms / 1000) -> None:
            await asyncio.sleep(d)
            log.append(f"{n}.init")

        async def boot(self: object, n: str = name) -> None:
            log.append(f"{n}.start")

        return cocoa(deps=deps or [])(
            type(name, (), {"prepare": on_init(prepare), "boot": on_start(boot)})
        )

    slow_init, fast_init = phased("Slow", 40), phased("Fast", 1)
    root = cocoa(deps=[slow_init, fast_init])(type("App", (), {}))

    async with Canary(root, start_concurrency=4):
        pass

    inits = [i for i, e in enumerate(log) if e.endswith(".init")]
    starts = [i for i, e in enumerate(log) if e.endswith(".start")]
    assert max(inits) < min(starts), f"栅栏被越过了: {log}"


async def test_concurrency_is_bounded() -> None:
    """信号量必须真的封顶——并发启动最经典的翻车是把下游打爆。"""
    inflight = 0
    peak = 0

    def counted(name: str, deps: list[type] | None = None) -> type:
        async def boot(self: object) -> None:
            nonlocal inflight, peak
            inflight += 1
            peak = max(peak, inflight)
            await asyncio.sleep(0.02)
            inflight -= 1

        return cocoa(deps=deps or [])(type(name, (), {"boot": on_start(boot)}))

    config = cocoa(type("Config", (), {}))
    leaves = [counted(f"IO{i}", [config]) for i in range(12)]
    root = cocoa(deps=leaves)(type("App", (), {}))

    async with Canary(root, start_concurrency=3):
        pass

    assert peak <= 3, f"同时最多 3 个，实际峰值 {peak}"


async def test_a_failure_still_reclaims_everything_that_entered() -> None:
    """并发下失败：进入过 @on_start 的单元（含被取消的）都要被回收，且逆序。"""
    reclaimed: list[str] = []

    def unit(name: str, ms: float, boom: bool = False, deps: list[type] | None = None) -> type:
        async def boot(self: object, d: float = ms / 1000, b: bool = boom) -> None:
            await asyncio.sleep(d)
            if b:
                raise RuntimeError("连不上下游")

        async def bye(self: object, n: str = name) -> None:
            reclaimed.append(n)

        return cocoa(deps=deps or [])(type(name, (), {"boot": on_start(boot), "bye": on_stop(bye)}))

    config = unit("Config", 0)  # 也带 @on_stop，用来验证依赖最后回收
    quick = unit("Quick", 1, deps=[config])
    boomer = unit("Boomer", 10, boom=True, deps=[config])
    slowest = unit("Slowest", 500, deps=[config])  # 会在 Boomer 炸掉时被取消
    root = cocoa(deps=[quick, boomer, slowest])(type("App", (), {}))

    canary = Canary(root, start_concurrency=4)
    with pytest.raises(RuntimeError, match="连不上下游"):
        await canary.start()

    assert canary.state.name == "FAILED"
    # 三个都进入过 @on_start（Slowest 是被取消的，但它可能已经拿了半个资源）
    assert set(reclaimed) == {"Config", "Quick", "Boomer", "Slowest"}
    # 依赖在后：Config 最后被回收
    assert reclaimed[-1] == "Config"


async def test_two_simultaneous_failures_are_both_reported() -> None:
    """真有两个单元同时失败时，一个都不隐瞒。"""

    def boomer(name: str, deps: list[type] | None = None) -> type:
        async def boot(self: object, n: str = name) -> None:
            await asyncio.sleep(0.01)
            raise RuntimeError(f"{n} 挂了")

        return cocoa(deps=deps or [])(type(name, (), {"boot": on_start(boot)}))

    config = cocoa(type("Config", (), {}))
    root = cocoa(deps=[boomer("A", [config]), boomer("B", [config])])(type("App", (), {}))

    with pytest.raises(ExceptionGroup) as caught:
        await Canary(root, start_concurrency=4).start()
    messages = {str(exc) for exc in caught.value.exceptions}
    assert messages == {"A 挂了", "B 挂了"}


async def test_a_lone_failure_looks_exactly_like_the_sequential_one() -> None:
    """只有一个单元失败时，异常必须原样抛出——调用方的 except RuntimeError 照旧管用。"""

    def boomer(name: str, deps: list[type] | None = None) -> type:
        async def boot(self: object) -> None:
            raise RuntimeError("就我一个挂了")

        return cocoa(deps=deps or [])(type(name, (), {"boot": on_start(boot)}))

    config = cocoa(type("Config", (), {}))
    root = cocoa(deps=[boomer("Only", [config])])(type("App", (), {}))

    with pytest.raises(RuntimeError, match="就我一个挂了") as caught:
        await Canary(root, start_concurrency=4).start()
    assert not isinstance(caught.value, ExceptionGroup)


def test_a_nonsense_concurrency_is_refused() -> None:
    @cocoa
    class Unit: ...

    with pytest.raises(ValueError, match="at least 1"):
        Canary(Unit, start_concurrency=0)
