"""stop() 是单元的动作：回收本单元与不再被需要的依赖，仍被依赖时拒绝。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, LifecycleError, dep, scope_of, start, stop

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
    await root.init()
    await root.start()
    log.clear()
    await root.stop()

    assert log == ["service.stop", "database.stop", "config.stop"]


async def test_stopping_a_unit_that_running_units_depend_on_is_refused() -> None:
    log: list[str] = []
    config = tracked("config", log)
    database = tracked("database", log, config)
    service = tracked("service", log, database)

    root = service()
    async with root:
        with pytest.raises(
            LifecycleError, match="database is still required by running units: service"
        ):
            await root.d0.stop()  # type: ignore[attr-defined]
        assert not [event for event in log if event.endswith(".stop")], "nothing was reclaimed"


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


async def test_an_explicitly_started_unit_outlives_the_root() -> None:
    log: list[str] = []
    config = tracked("config", log)
    metrics = tracked("metrics", log, config)
    database = tracked("database", log, config)
    service = tracked("service", log, database, metrics)

    root = service()
    await root.init()
    await root.start()
    await root.d1.start()  # type: ignore[attr-defined]  # metrics：显式要求运行
    log.clear()

    await root.stop()
    assert log == ["service.stop", "database.stop"], "metrics and the config it needs stay up"

    log.clear()
    await root.d1.stop()  # type: ignore[attr-defined]
    assert log == ["metrics.stop", "config.stop"]


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
    assert scope_of(root).entered["start"].keys() >= {database}
    await substitute.stop()
    assert not scope_of(root).entered["start"]
