"""整条生命周期：四个动作、栅栏、失败回滚、两种入口写法。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, dep, init, start, stop

pytestmark = pytest.mark.functional


async def test_entering_a_unit_brings_up_its_whole_graph_and_leaving_reclaims_it() -> None:
    seen: list[str] = []

    class Config(Canary):
        @init
        def load(self) -> None:
            seen.append("config.init")
            self.dsn = "memory://"

    class Database(Canary):
        config = dep(Config)

        @start
        async def connect(self) -> None:
            seen.append(f"database.start({self.config.dsn})")

        @stop
        async def close(self) -> None:
            seen.append("database.stop")

    class Service(Canary):
        database = dep(Database)

        @start
        async def go(self) -> None:
            seen.append("service.start")

        @stop
        async def bye(self) -> None:
            seen.append("service.stop")

    async with Service() as service:
        seen.append("body")
        assert service.database.config.dsn == "memory://"

    assert seen == [
        "config.init",
        "database.start(memory://)",
        "service.start",
        "body",
        "service.stop",
        "database.stop",
    ]


async def test_every_init_completes_before_any_start_runs() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @init
        def prepare(self) -> None:
            seen.append("leaf.init")

        @start
        def go(self) -> None:
            seen.append("leaf.start")

    class Root(Canary):
        leaf = dep(Leaf)

        @init
        def prepare(self) -> None:
            seen.append("root.init")

        @start
        def go(self) -> None:
            seen.append("root.start")

    async with Root():
        pass

    assert seen[:2] == ["leaf.init", "root.init"]
    assert seen[2:] == ["leaf.start", "root.start"]


async def test_a_failure_during_start_reclaims_what_already_started() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @start
        def go(self) -> None:
            seen.append("leaf.start")

        @stop
        def bye(self) -> None:
            seen.append("leaf.stop")

    class Root(Canary):
        leaf = dep(Leaf)

        @start
        def go(self) -> None:
            raise RuntimeError("no")

        @stop
        def bye(self) -> None:
            seen.append("root.stop")

    with pytest.raises(RuntimeError, match="no"):
        async with Root():
            pass

    # 进入过 @start 的单元都回收，包括失败的那一个。
    assert seen == ["leaf.start", "root.stop", "leaf.stop"]


async def test_a_rollback_failure_rides_along_as_a_note_on_the_original_error() -> None:
    class Leaf(Canary):
        @start
        def go(self) -> None: ...

        @stop
        def bye(self) -> None:
            raise RuntimeError("stop failed too")

    class Root(Canary):
        leaf = dep(Leaf)

        @start
        def go(self) -> None:
            raise RuntimeError("start failed")

    with pytest.raises(RuntimeError, match="start failed") as caught:
        async with Root():
            pass

    assert any("stop failed too" in note for note in caught.value.__notes__)


async def test_a_failure_during_init_has_nothing_to_reclaim() -> None:
    seen: list[str] = []

    class Leaf(Canary):
        @init
        def prepare(self) -> None:
            raise RuntimeError("bad config")

        @stop
        def bye(self) -> None:
            seen.append("leaf.stop")

    class Root(Canary):
        leaf = dep(Leaf)

    with pytest.raises(RuntimeError, match="bad config"):
        async with Root():
            pass

    assert seen == []


async def test_the_explicit_four_steps_match_the_context_manager() -> None:
    seen: list[str] = []

    class Unit(Canary):
        @init
        def prepare(self) -> None:
            seen.append("init")

        @start
        def go(self) -> None:
            seen.append("start")

        @stop
        def bye(self) -> None:
            seen.append("stop")

    unit = Unit()
    await unit.init()
    await unit.start()
    await unit.stop()

    assert seen == ["init", "start", "stop"]


async def test_a_unit_may_override_a_lifecycle_method_and_compose_with_super() -> None:
    seen: list[str] = []

    class Traced(Canary):
        async def start(self) -> None:
            seen.append("before")
            await super().start()
            seen.append("after")

    class Service(Traced):
        @start
        def go(self) -> None:
            seen.append("hook")

    service = Service()
    await service.init()
    await service.start()

    assert seen == ["before", "hook", "after"]
    assert isinstance(service, Canary)


async def test_async_with_goes_through_the_units_own_lifecycle_methods() -> None:
    seen: list[str] = []

    class Traced(Canary):
        async def start(self) -> None:
            seen.append("before")
            await super().start()
            seen.append("after")

    class Service(Traced):
        @start
        def go(self) -> None:
            seen.append("hook")

    async with Service():
        pass

    assert seen == ["before", "hook", "after"]
