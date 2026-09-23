"""stop() 是单元的动作：先停自己，再停不再被需要的依赖；仍被依赖时拒绝。"""

from __future__ import annotations

import asyncio

import pytest

from canary_framework import (
    Canary,
    CircularDependencyError,
    LifecycleError,
    dep,
    init,
    scope_of,
    start,
    stop,
)

pytestmark = pytest.mark.functional


def tracked(name: str, log: list[str], *deps: type[Canary]) -> type[Canary]:
    """A unit that records its start and stop, depending on *deps*."""

    def on_start(self: Canary) -> None:
        log.append(f"{name}.start")

    def on_stop(self: Canary) -> None:
        log.append(f"{name}.stop")

    namespace: dict[str, object] = {f"d{i}": dep(d) for i, d in enumerate(deps)}
    namespace["on_start"] = start(on_start)
    namespace["on_stop"] = stop(on_stop)
    return type(name, (Canary,), namespace)


async def test_stopping_the_root_reclaims_the_whole_graph_in_reverse() -> None:
    log: list[str] = []
    config = tracked("config", log)
    database = tracked("database", log, config)
    service = tracked("service", log, database)

    root = service()
    async with root:
        log.clear()

    assert log == ["service.stop", "database.stop", "config.stop"]


async def test_stopping_a_unit_still_in_use_is_skipped() -> None:
    log: list[str] = []
    c = tracked("c", log)
    a = tracked("a", log, c)
    b = tracked("b", log, c)
    x = tracked("x", log, a, b)

    root = x()
    async with root:
        log.clear()
        await root.d0.stop()  # type: ignore[attr-defined]  # a：仍被 x 使用
        assert log == [], "a is used by x, and c by a and b: nothing stops"
    assert log == ["x.stop", "a.stop", "b.stop", "c.stop"]


async def test_stopping_a_unit_and_its_user_together_stops_each_once() -> None:
    log: list[str] = []
    c = tracked("c", log)
    a = tracked("a", log, c)
    b = tracked("b", log, c)
    x = tracked("x", log, a, b)

    root = x()
    await root.init()
    await root.start()
    log.clear()
    await asyncio.gather(root.d0.stop(), root.stop())  # type: ignore[attr-defined]

    assert sorted(log) == ["a.stop", "b.stop", "c.stop", "x.stop"]
    assert log[0] == "x.stop" and log[-1] == "c.stop"


async def test_a_unit_started_on_its_own_can_be_stopped_on_its_own() -> None:
    log: list[str] = []
    config = tracked("config", log)
    database = tracked("database", log, config)
    service = tracked("service", log, database)

    root = service()
    await root.init()
    db = root.d0  # type: ignore[attr-defined]
    await db.start()
    await db.stop()

    assert log == ["config.start", "database.start", "database.stop", "config.stop"]


async def test_a_shared_dependency_stays_until_its_last_user_stops() -> None:
    log: list[str] = []
    shared = tracked("shared", log)
    left = tracked("left", log, shared)
    right = tracked("right", log, shared)
    root_cls = tracked("root", log, left, right)

    root = root_cls()
    await root.init()
    await root.d0.start()  # type: ignore[attr-defined]
    await root.d1.start()  # type: ignore[attr-defined]
    log.clear()

    await root.d0.stop()  # type: ignore[attr-defined]
    assert log == ["left.stop"], "right still needs shared"
    await root.d1.stop()  # type: ignore[attr-defined]
    assert log == ["left.stop", "right.stop", "shared.stop"]


async def test_a_unit_started_directly_inside_a_graph_stops_with_its_root() -> None:
    log: list[str] = []
    config = tracked("config", log)
    metrics = tracked("metrics", log, config)
    service = tracked("service", log, metrics)

    root = service()
    async with root:
        await root.d0.start()  # type: ignore[attr-defined]  # 已在运行：空操作
        log.clear()

    assert log == ["service.stop", "metrics.stop", "config.stop"]


async def test_independent_units_stop_concurrently() -> None:
    entered: dict[str, asyncio.Event] = {"left": asyncio.Event(), "right": asyncio.Event()}

    def stops_with(me: str, other: str) -> type[Canary]:
        async def on_stop(self: Canary) -> None:
            entered[me].set()
            await entered[other].wait()  # 串行回收时这里会永远等下去

        return type(me, (Canary,), {"on_stop": stop(on_stop)})

    left, right = stops_with("left", "right"), stops_with("right", "left")

    class Root(Canary):
        left_unit = dep(left)
        right_unit = dep(right)

    async with asyncio.timeout(1):
        async with Root():
            pass


async def test_a_provided_substitute_is_started_and_stopped_under_the_type_it_replaces() -> None:
    log: list[str] = []
    config = tracked("config", log)
    database = tracked("database", log, config)
    service = tracked("service", log, database)
    fake_database = type("FakeDatabase", (database,), {})

    root = service()
    substitute = fake_database()
    scope_of(root).provide(database, substitute)
    await root.init()
    await substitute.start()
    assert database in scope_of(root).entered["start"]
    await substitute.stop()
    assert not scope_of(root).entered["start"]


async def test_a_cycle_is_reported_before_any_hook_runs() -> None:
    log: list[str] = []

    class Innocent(Canary):
        @init
        def load(self) -> None:
            log.append("innocent.init")

    class A(Canary): ...

    class B(Canary):
        a = dep(A)

    A.b = dep(B)  # type: ignore[attr-defined]

    class Root(Canary):
        innocent = dep(Innocent)
        a = dep(A)

    with pytest.raises(CircularDependencyError, match="Root -> A -> B -> A"):
        await Root().init()
    assert log == []


async def test_a_missing_predecessor_is_reported_before_any_hook_runs() -> None:
    log: list[str] = []
    config = tracked("config", log)
    service = tracked("service", log, config)

    root = service()
    only_config = scope_of(root).instance(config)
    await only_config.init()  # type: ignore[attr-defined]  # 只初始化了 config
    with pytest.raises(LifecycleError, match="@init has not run"):
        await root.start()
    assert log == [], "config did not start while service could not"


def failing(name: str, log: list[str], *deps: type[Canary]) -> type[Canary]:
    """A unit whose @start fails after recording itself."""

    def on_start(self: Canary) -> None:
        log.append(f"{name}.start")
        raise RuntimeError(f"{name} failed")

    def on_stop(self: Canary) -> None:
        log.append(f"{name}.stop")

    namespace: dict[str, object] = {f"d{i}": dep(d) for i, d in enumerate(deps)}
    namespace["on_start"] = start(on_start)
    namespace["on_stop"] = stop(on_stop)
    return type(name, (Canary,), namespace)


async def test_a_failed_start_releases_itself_then_what_its_users_acquired() -> None:
    log: list[str] = []
    c = tracked("c", log)
    a = tracked("a", log, c)
    b = failing("b", log, c)
    x = tracked("x", log, a, b)

    root = x()
    await root.init()
    with pytest.raises(RuntimeError, match="b failed"):
        await root.start()

    # b 立即回滚自己；x 依赖不足，不启动，释放它占用的 a；最后没人使用 c
    assert log == ["c.start", "a.start", "b.start", "b.stop", "a.stop", "c.stop"]
    assert not scope_of(root).entered["start"], "nothing is left running"


async def test_a_sibling_still_starting_finishes_before_it_is_released() -> None:
    log: list[str] = []

    class Slow(Canary):
        @start
        async def connect(self) -> None:
            log.append("slow.start")
            await asyncio.sleep(0.01)
            log.append("slow.started")

        @stop
        def close(self) -> None:
            log.append("slow.stop")

    broken = failing("broken", log)

    class Root(Canary):
        slow = dep(Slow)
        other = dep(broken)

    root = Root()
    await root.init()
    with pytest.raises(RuntimeError, match="broken failed"):
        await root.start()

    assert "slow.started" in log, "the sibling was not cancelled halfway"
    assert log.index("slow.started") < log.index("slow.stop")


async def test_a_cancelled_start_releases_what_it_acquired() -> None:
    log: list[str] = []
    gate = asyncio.Event()

    class Fast(Canary):
        @start
        def connect(self) -> None:
            log.append("fast.start")

        @stop
        def close(self) -> None:
            log.append("fast.stop")

    class Hanging(Canary):
        fast = dep(Fast)

        @start
        async def connect(self) -> None:
            log.append("hanging.start")
            gate.set()
            await asyncio.Event().wait()

        @stop
        def close(self) -> None:
            log.append("hanging.stop")

    root = Hanging()
    await root.init()
    starting = asyncio.create_task(root.start())
    await gate.wait()
    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await starting

    assert log == ["fast.start", "hanging.start", "hanging.stop", "fast.stop"]


async def test_a_custom_phase_with_undo_is_rolled_back_on_failure() -> None:
    from canary_framework import Phase, advance

    rollback = Phase("rollback")
    migrate = Phase("migrate", after=init, undo=rollback)
    log: list[str] = []

    class Schema(Canary):
        @migrate
        def apply(self) -> None:
            log.append("schema.migrate")

        @rollback
        def revert(self) -> None:
            log.append("schema.rollback")

    class Data(Canary):
        schema = dep(Schema)

        @migrate
        def apply(self) -> None:
            raise RuntimeError("data failed")

        @rollback
        def revert(self) -> None:
            log.append("data.rollback")

    root = Data()
    await root.init()
    with pytest.raises(RuntimeError, match="data failed"):
        await advance(root, migrate)
    assert log == ["schema.migrate", "data.rollback", "schema.rollback"]


async def test_a_rollback_failure_during_cancellation_goes_to_the_loop_handler() -> None:
    reported: list[BaseException] = []
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _loop, context: reported.append(context["exception"]))
    gate = asyncio.Event()

    class Leaky(Canary):
        @start
        def connect(self) -> None: ...

        @stop
        def close(self) -> None:
            raise RuntimeError("close failed")

    class Hanging(Canary):
        leaky = dep(Leaky)

        @start
        async def connect(self) -> None:
            gate.set()
            await asyncio.Event().wait()

    root = Hanging()
    await root.init()
    starting = asyncio.create_task(root.start())
    await gate.wait()
    starting.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await starting
    finally:
        loop.set_exception_handler(None)

    assert [str(exc) for exc in reported] == ["close failed"]


async def test_a_stop_cut_short_by_a_timeout_carries_on_when_called_again() -> None:
    log: list[str] = []
    stuck = True

    class Config(Canary):
        @stop
        def close(self) -> None:
            log.append("config.stop")

    class Database(Canary):
        config = dep(Config)

        @stop
        async def close(self) -> None:
            log.append("database.stop")
            if stuck:
                await asyncio.Event().wait()

    class Service(Canary):
        database = dep(Database)

        @stop
        def close(self) -> None:
            log.append("service.stop")

    service = Service()
    await service.init()
    await service.start()
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await service.stop()
    assert log == ["service.stop", "database.stop"], "config was not reached"
    assert Config in scope_of(service).entered["start"]

    stuck = False
    await service.stop()
    assert log == ["service.stop", "database.stop", "config.stop"]
