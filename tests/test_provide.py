"""替换依赖：provide 登记的实例在整张图上生效，并按自身类型参与生命周期。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, LifecycleError, dep, init, scope_of, start, stop

pytestmark = pytest.mark.integration


class Config(Canary):
    @init
    def load(self) -> None:
        self.dsn = "real://"


class Database(Canary):
    config = dep(Config)

    @start
    def connect(self) -> None:
        self.backend = "real"

    @stop
    def close(self) -> None:
        self.backend = "closed"


class Repository(Canary):
    database = dep(Database)


class Service(Canary):
    database = dep(Database)
    repository = dep(Repository)


async def test_a_provided_unit_replaces_the_dependency_across_the_whole_graph() -> None:
    class FakeDatabase(Database): ...

    service = Service()
    fake = FakeDatabase()
    scope_of(service).provide(Database, fake)

    async with service:
        assert service.database is fake
        assert service.repository.database is fake


async def test_a_provided_unit_runs_its_own_hooks_and_reads_its_own_dependencies() -> None:
    seen: list[str] = []

    class FakeDatabase(Database):
        @start
        def connect(self) -> None:
            seen.append(f"fake.start({self.config.dsn})")

        @stop
        def close(self) -> None:
            seen.append("fake.stop")

    service = Service()
    scope_of(service).provide(Database, FakeDatabase())
    async with service:
        pass

    assert seen == ["fake.start(real://)", "fake.stop"]


async def test_a_provided_unit_enters_the_dependencies_its_own_type_declares() -> None:
    seen: list[str] = []

    class Clock(Canary):
        @init
        def load(self) -> None:
            seen.append("clock.init")

    class FakeDatabase(Database):
        clock = dep(Clock)

    service = Service()
    scope_of(service).provide(Database, FakeDatabase())
    await service.init()

    assert seen == ["clock.init"]


async def test_providing_after_the_dependency_exists_is_refused() -> None:
    service = Service()
    await service.init()

    with pytest.raises(LifecycleError, match="already has a Database"):
        scope_of(service).provide(Database, Database())


async def test_providing_an_instance_of_another_type_is_refused() -> None:
    with pytest.raises(TypeError, match="is not a Database"):
        scope_of(Service()).provide(Database, Config())


async def test_providing_a_unit_that_belongs_to_another_scope_is_refused() -> None:
    other = Service()
    await other.init()

    with pytest.raises(LifecycleError, match="another scope"):
        scope_of(Service()).provide(Database, other.database)


async def test_assigning_to_a_dependency_is_refused_with_a_pointer_to_provide() -> None:
    service = Service()
    await service.init()

    with pytest.raises(AttributeError, match=r"provide\(Database, replacement\)"):
        service.database = Database()
