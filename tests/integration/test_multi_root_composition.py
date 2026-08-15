"""Integration — composing multiple roots that share a dependency subgraph."""

import pytest

from canary_framework import Canary, cocoa, on_start

pytestmark = pytest.mark.integration


async def test_composed_roots_share_singletons() -> None:
    @cocoa
    class Config:
        pass

    @cocoa(deps=[Config])
    class Database:
        pass

    @cocoa(deps=[Database])
    class UserRepo:
        pass

    @cocoa(deps=[Database])
    class OrderRepo:
        pass

    async with Canary(UserRepo, OrderRepo) as canary:
        assert set(canary.order) == {Config, Database, UserRepo, OrderRepo}
        # 拓扑约束：Config → Database → {UserRepo, OrderRepo}
        assert canary.order.index(Config) < canary.order.index(Database)
        assert canary.order.index(Database) < canary.order.index(UserRepo)
        assert canary.order.index(Database) < canary.order.index(OrderRepo)

        # 共享的依赖子图被实例化为同一批单例。
        assert canary[UserRepo].database is canary[Database]
        assert canary[OrderRepo].database is canary[Database]
        assert canary[UserRepo].database.config is canary[Config]
        assert canary[OrderRepo].database.config is canary[Config]


async def test_standalone_leaf_runs_without_a_dependency_graph() -> None:
    events: list[str] = []

    @cocoa
    class Leaf:
        @on_start
        def start(self) -> None:
            events.append("leaf.start")

    async with Canary(Leaf) as canary:
        assert canary.order == (Leaf,)
        assert canary.state.name == "STARTED"

    assert events == ["leaf.start"]
