"""running()：带替身启动一张图，退出时回收。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, dep, start, stop
from canary_framework.test import running, unit

pytestmark = pytest.mark.integration

events: list[str] = []


class Clock(Canary):
    def now(self) -> float:
        raise AssertionError("the real clock must never be used in a test")


class ManualClock(Clock):
    at = 0.0

    def now(self) -> float:
        return self.at

    @start
    def wind(self) -> None:
        events.append("clock start")

    @stop
    def unwind(self) -> None:
        events.append("clock stop")


class Database(Canary):
    @start
    def connect(self) -> None:
        events.append("db start")

    @stop
    def close(self) -> None:
        events.append("db stop")


class Service(Canary):
    clock = dep(Clock)
    database = dep(Database)


@pytest.fixture(autouse=True)
def _clear() -> None:
    events.clear()


async def test_it_starts_the_graph_and_reclaims_it_on_exit() -> None:
    async with running(Service) as service:
        assert isinstance(service, Service)
        assert events == ["db start"]
    assert events == ["db start", "db stop"]


async def test_a_double_stands_in_and_runs_its_own_hooks() -> None:
    clock = ManualClock()
    async with running(Service, {Clock: clock}) as service:
        assert service.clock is clock
        assert unit(service, Clock) is clock
        clock.at = 42.0
        assert service.clock.now() == 42.0
    assert sorted(events) == ["clock start", "clock stop", "db start", "db stop"]


async def test_every_call_is_a_fresh_graph() -> None:
    async with running(Service) as first, running(Service) as second:
        assert first is not second
        assert first.database is not second.database


async def test_the_graph_is_reclaimed_when_the_body_raises() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with running(Service):
            raise RuntimeError("boom")
    assert events == ["db start", "db stop"]


async def test_a_double_of_the_wrong_type_is_rejected_before_anything_starts() -> None:
    with pytest.raises(TypeError, match="is not a Clock"):
        async with running(Service, {Clock: Database()}):
            raise AssertionError("unreachable")
    assert events == []
