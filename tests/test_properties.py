"""性质测试：随机依赖图 × 随机钩子行为 × 随机调用时序，断言生命周期的不变量。

图、每个钩子让出事件循环的次数与是否失败、调用方的时序（正常进出、``start()`` 进行中
``stop()``、``start()`` 进行中被取消、停止后再次启动、随机启动与停止部分单元、只调用
``start()``）都由 hypothesis 生成。耗时用"让出事件循环若干次"表示而不是真实的时间，因此每个例子都是确定的，
失败时可以稳定复现。

每个场景结束时都会再 ``stop()`` 一次，代表应用最终关闭。之后检查：

1. **配对**：每个单元的事件序列形如 ``(start_begin [start_end] stop)*``——每次进入 ``@start``
   恰好被回收一次，且启动完成（如果完成了）一定早于回收，不会有资源在回收之后才获取。
   失败或被取消的 ``@start`` 在下一次进入之前一定已被回收。
2. **回收安全**：回收一个单元时，依赖它且仍持有资源的单元都已回收。
3. **推进顺序**：一个单元开始某个阶段时，它的依赖都已完成该阶段。
4. **``@init`` 只运行一次**。
5. **异常如实**：调用方收到的异常都来自钩子，框架内部的异常不外泄；有钩子失败时调用方
   一定收到异常。
6. **停止一个单元**：``stop()`` 返回后，它仍持有资源当且仅当它仍被使用。
7. **失败的启动自行回收**：``start()`` 失败返回时，它为此获取的一切都已释放。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from canary_framework import Canary, dep, init, scope_of, start, stop

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
    #: "partial" 场景中依次直接启动、再依次停止的单元
    starts: tuple[int, ...] = ()
    stops: tuple[int, ...] = ()


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
    kind = draw(
        st.sampled_from(
            ["context", "stop_during_start", "cancel_start", "restart", "partial", "bare_start"]
        )
    )
    picks = st.lists(st.integers(0, size - 1), max_size=size + 2)
    starts, stops = (draw(picks), draw(picks)) if kind == "partial" else ([], [])
    return Scenario(tuple(units), kind, draw(st.integers(0, 12)), tuple(starts), tuple(stops))


Event = tuple[int, str]


def build(units: tuple[UnitSpec, ...], log: list[Event]) -> type[Canary]:
    """Build one Canary class per spec, plus a root that depends on all of them."""

    def hook(index: int, phase: str, spec: Hook):  # type: ignore[no-untyped-def]
        async def run(self: Canary) -> None:
            log.append((index, f"{phase}_begin" if phase != "stop" else "stop"))
            try:
                for _ in range(spec.ticks):
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                log.append((index, f"{phase}_cancel"))
                raise
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
    root = type("Root", (Canary,), {f"d{i}": dep(c) for i, c in enumerate(classes)})
    root.units = classes  # type: ignore[attr-defined]
    return root


async def settle(awaitable: object, caught: list[BaseException]) -> None:
    try:
        await awaitable  # type: ignore[misc]
    except BaseException as exc:  # 收集一切，由不变量判断是否合理
        caught.append(exc)


async def drive(
    scenario: Scenario, root: Canary, caught: list[BaseException], log: list[Event]
) -> None:
    async def ticks(n: int) -> None:
        for _ in range(n):
            await asyncio.sleep(0)

    # 无法抛给调用方的错误（被取消的推进回滚时撤销钩子的失败）交给事件循环的异常处理器
    asyncio.get_running_loop().set_exception_handler(
        lambda _loop, context: (
            caught.append(context["exception"]) if "exception" in context else None
        )
    )

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
        case "partial":
            await settle(root.init(), caught)
            if not caught:
                scope = scope_of(root)
                units = [scope.instance(cls) for cls in type(root).units]  # type: ignore[attr-defined]
                for index in scenario.starts:
                    await settle(units[index].start(), caught)  # type: ignore[attr-defined]
                for index in scenario.stops:
                    await settle(units[index].stop(), caught)  # type: ignore[attr-defined]
                    log.append((index, "stop_returned"))
        case "bare_start":
            await settle(root.init(), caught)
            if not caught:
                before = len(caught)
                await settle(root.start(), caught)
                if len(caught) > before:
                    log.append((-1, "start_failed"))
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

    # 1. 配对：(start_begin [start_end] stop)*；失败或被取消之后只能是 stop
    watched = {"start_begin", "start_end", "start_raise", "start_cancel", "stop"}
    for index in range(len(units)):
        sequence = [e for i, e in log if i == index and e in watched]
        state = "idle"
        for event in sequence:
            match state, event:
                case "idle", "start_begin":
                    state = "starting"
                case "starting", "start_end":
                    state = "started"
                case "starting", ("start_raise" | "start_cancel"):
                    state = "failed"
                case (("starting" | "started" | "failed"), "stop"):
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
            case "stop_returned":
                in_use = any(j in holding for j in dependents[index])
                assert (index in holding) == in_use, (
                    f"U{index} holds={index in holding} while in use={in_use} after stop()"
                )
            case "start_failed":
                assert not holding, f"a failed start() left {sorted(holding)} running"

    # 5. 异常如实：只有钩子的失败（或取消），同一个失败不重复报告
    allowed = (HookError, asyncio.CancelledError)
    for exc in caught:
        found = leaves(exc)
        for leaf in found:
            assert isinstance(leaf, allowed), f"framework error leaked: {leaf!r}"
        reported = [leaf for leaf in found if isinstance(leaf, HookError)]
        assert len({id(leaf) for leaf in reported}) == len(reported), f"reported twice: {exc!r}"
    if any(event.endswith("_raise") for _, event in log):
        # 回滚中撤销钩子的失败以 note 附在引发回滚的异常上（被取消时即 CancelledError）
        notes = [
            note
            for exc in caught
            for leaf in leaves(exc)
            for note in getattr(leaf, "__notes__", ())
        ]
        assert any(isinstance(leaf, HookError) for exc in caught for leaf in leaves(exc)) or any(
            "HookError" in note for note in notes
        ), "a hook failed but no caller saw the failure"


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
    asyncio.run(drive(scenario, root, caught, log))
    check(scenario, log, caught)
