"""unit()：按类型取回图上的实例。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, dep, scope_of
from canary_framework.test import unit

pytestmark = pytest.mark.integration


class Store(Canary): ...


class Collector(Canary):
    store = dep(Store)


class Daemon(Canary):
    collector = dep(Collector)


async def test_it_reaches_a_unit_the_root_never_declared() -> None:
    async with Daemon() as daemon:
        assert unit(daemon, Store) is daemon.collector.store


async def test_any_unit_of_the_graph_can_be_the_starting_point() -> None:
    async with Daemon() as daemon:
        assert unit(daemon.collector.store, Daemon) is daemon


async def test_it_returns_the_double_when_one_was_provided() -> None:
    class FakeStore(Store): ...

    daemon, fake = Daemon(), FakeStore()
    scope_of(daemon).provide(Store, fake)
    async with daemon:
        assert unit(daemon, Store) is fake


def test_before_the_lifecycle_begins_only_the_root_is_there() -> None:
    daemon = Daemon()
    assert unit(daemon, Daemon) is daemon
    with pytest.raises(LookupError, match="no Store in this graph"):
        unit(daemon, Store)
