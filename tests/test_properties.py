"""性质测试：随机依赖图 × 随机钩子行为 × 随机调用时序，断言生命周期的不变量。

图、每个钩子让出事件循环的次数与是否失败、调用方的时序（正常进出、``start()`` 进行中
``stop()``、``start()`` 进行中被取消、停止后再次启动）都由 hypothesis 生成。耗时用"让出
事件循环若干次"表示而不是真实的时间，因此每个例子都是确定的，失败时可以稳定复现。

每个场景结束时都会再 ``stop()`` 一次，代表应用最终关闭。之后检查：

1. **配对**：每个单元的事件序列形如 ``(start_begin [start_end] stop)*``——每次进入 ``@start``
   恰好被回收一次，且启动完成（如果完成了）一定早于回收，不会有资源在回收之后才获取。
2. **回收安全**：回收一个单元时，依赖它且仍持有资源的单元都已回收。
3. **推进顺序**：一个单元开始某个阶段时，它的依赖都已完成该阶段。
4. **``@init`` 只运行一次**。
5. **异常如实**：调用方收到的异常都来自钩子，框架内部的异常不外泄；有钩子失败时调用方
   一定收到异常。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from canary_framework import Canary, dep, init, start, stop

pytestmark = pytest.mark.integration


class HookError(Exception):
    """钩子按剧本抛出的异常；调用方只应收到这一种（或由它组成的异常组）。"""


@dataclass(frozen=True)
class Hook:
    ticks: int
    fails: bool


@dataclass(frozen=True)
class UnitSpec:
    deps: tuple[int, ...]
    init: Hook
    start: Hook
    stop: Hook


@dataclass(frozen=True)
class Scenario:
    units: tuple[UnitSpec, ...]
    kind: str
    trigger: int


rare_failure = st.builds(
    Hook, ticks=st.integers(0, 3), fails=st.integers(0, 4).map(lambda n: n == 0)
)


@st.composite
def scenarios(draw: st.DrawFn) -> Scenario:
    size = draw(st.integers(1, 7))
    units = []
    for index in range(size):
        # 只依赖编号更小的单元，保证无环
        deps = draw(st.sets(st.integers(0, index - 1), max_size=3)) if index else set()
        units.append(
            UnitSpec(
                deps=tuple(sorted(deps)),
                init=draw(rare_failure),
                start=draw(rare_failure),
                stop=draw(rare_failure),
            )
        )
    kind = draw(st.sampled_from(["context", "stop_during_start", "cancel_start", "restart"]))
    return Scenario(tuple(units), kind, draw(st.integers(0, 12)))


Event = tuple[int, str]


def build(units: tuple[UnitSpec, ...], log: list[Event]) -> type[Canary]:
    """Build one Canary class per spec, plus a root that depends on all of them."""

    def hook(index: int, phase: str, spec: Hook):  # type: ignore[no-untyped-def]
        async def run(self: Canary) -> None:
            log.append((index, f"{phase}_begin" if phase != "stop" else "stop"))
            for _ in range(spec.ticks):
                await asyncio.sleep(0)
            if spec.fails:
                log.append((index, f"{phase}_raise"))
                raise HookError(f"U{index}.{phase}")
            if phase != "stop":
                log.append((index, f"{phase}_end"))

        return run

    classes: list[type[Canary]] = []
    for index, spec in enumerate(units):
        namespace: dict[str, object] = {f"d{d}": dep(classes[d]) for d in spec.deps}
        namespace["on_init"] = init(hook(index, "init", spec.init))
        namespace["on_start"] = start(hook(index, "start", spec.start))
        namespace["on_stop"] = stop(hook(index, "stop", spec.stop))
        classes.append(type(f"U{index}", (Canary,), namespace))
    return type("Root", (Canary,), {f"d{i}": dep(c) for i, c in enumerate(classes)})


async def settle(awaitable: object, caught: list[BaseException]) -> None:
    try:
        await awaitable  # type: ignore[misc]
    except BaseException as exc:  # 收集一切，由不变量判断是否合理
        caught.append(exc)


async def drive(scenario: Scenario, root: Canary, caught: list[BaseException]) -> None:
    async def ticks(n: int) -> None:
        for _ in range(n):
            await asyncio.sleep(0)

    match scenario.kind:
        case "context":
            await settle(_enter_and_leave(root), caught)
        case "restart":
            await settle(_enter_and_leave(root), caught)
            await settle(_enter_and_leave(root), caught)
        case "stop_during_start":
            await settle(root.init(), caught)
            if not caught:
                starting = asyncio.create_task(root.start())
                await ticks(scenario.trigger)
                await settle(root.stop(), caught)
                await settle(starting, caught)
        case "cancel_start":
            await settle(root.init(), caught)
            if not caught:
                starting = asyncio.create_task(root.start())
                await ticks(scenario.trigger)
                starting.cancel()
                await settle(starting, caught)
    await settle(root.stop(), caught)  # 应用最终关闭


async def _enter_and_leave(root: Canary) -> None:
    async with root:
        pass


def leaves(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for inner in exc.exceptions for leaf in leaves(inner)]
    return [exc]


def check(scenario: Scenario, log: list[Event], caught: list[BaseException]) -> None:
    units = scenario.units
    dependents = {i: [j for j, u in enumerate(units) if i in u.deps] for i in range(len(units))}

    # 1. 配对：(start_begin [start_end] stop)*
    for index in range(len(units)):
        sequence = [e for i, e in log if i == index and e in {"start_begin", "start_end", "stop"}]
        state = "idle"
        for event in sequence:
            match state, event:
                case "idle", "start_begin":
                    state = "starting"
                case "starting", "start_end":
                    state = "started"
                case (("starting" | "started"), "stop"):
                    state = "idle"
                case _:
                    raise AssertionError(f"U{index}: {event!r} while {state}: {sequence}")
        assert state == "idle", f"U{index} still holds its resource: {sequence}"

    # 2/3/4. 按时刻检查回收安全、推进顺序与 @init 次数
    holding: set[int] = set()
    done: dict[str, set[int]] = {"init": set(), "start": set()}
    for index, event in log:
        match event:
            case "start_begin":
                missing = [d for d in units[index].deps if d not in done["start"]]
                assert not missing, f"U{index} started before its dependencies {missing}"
                holding.add(index)
            case "init_begin":
                assert index not in done["init"], f"U{index}.init ran twice"
                missing = [d for d in units[index].deps if d not in done["init"]]
                assert not missing, f"U{index} initialised before its dependencies {missing}"
            case "init_end":
                done["init"].add(index)
            case "start_end":
                done["start"].add(index)
            case "stop":
                still = [j for j in dependents[index] if j in holding]
                assert not still, f"U{index} reclaimed while {still} still depend on it"
                holding.discard(index)
                done["start"].discard(index)

    # 5. 异常如实：只有钩子的失败（或取消），同一个失败不重复报告
    allowed = (HookError, asyncio.CancelledError)
    for exc in caught:
        found = leaves(exc)
        for leaf in found:
            assert isinstance(leaf, allowed), f"framework error leaked: {leaf!r}"
        reported = [leaf for leaf in found if isinstance(leaf, HookError)]
        assert len({id(leaf) for leaf in reported}) == len(reported), f"reported twice: {exc!r}"
    if any(event.endswith("_raise") for _, event in log):
        assert any(isinstance(leaf, HookError) for exc in caught for leaf in leaves(exc)), (
            "a hook failed but no caller saw the failure"
        )


OK, FAIL = Hook(ticks=0, fails=False), Hook(ticks=0, fails=True)

#: hypothesis 找到过的最小失败用例，固定为回归例子。
#: 失败的依赖经两条路径到达时被运行了两次（失败记录被过早清除）。
REACHED_TWICE = Scenario(
    units=(UnitSpec((), OK, FAIL, FAIL), UnitSpec((0,), OK, FAIL, FAIL)),
    kind="context",
    trigger=0,
)
#: 等待共享推进的任务被取消时连带取消了该推进，推进结束时抛出 InvalidStateError。
WAITER_CANCELLED = Scenario(
    units=(
        UnitSpec((), FAIL, FAIL, FAIL),
        UnitSpec((), FAIL, FAIL, FAIL),
        UnitSpec((), FAIL, FAIL, FAIL),
        UnitSpec((0, 1), FAIL, FAIL, FAIL),
        UnitSpec((0, 1, 3), FAIL, FAIL, FAIL),
    ),
    kind="context",
    trigger=0,
)


@example(REACHED_TWICE)
@example(WAITER_CANCELLED)
@settings(
    max_examples=400,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(scenarios())
def test_lifecycle_invariants_hold_for_any_graph_and_timing(scenario: Scenario) -> None:
    log: list[Event] = []
    caught: list[BaseException] = []
    root = build(scenario.units, log)()
    asyncio.run(drive(scenario, root, caught))
    check(scenario, log, caught)
