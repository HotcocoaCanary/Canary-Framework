"""Integration — an async multi-tier app driven through its full lifecycle."""

import asyncio

import pytest

from canary_framework import Canary, LifecycleState, cocoa, on_init, on_start, on_stop

pytestmark = pytest.mark.integration


async def test_async_full_lifecycle_order_and_sharing() -> None:
    events: list[str] = []

    @cocoa
    class Config:
        @on_init
        async def load(self) -> None:
            await asyncio.sleep(0)
            events.append("config.load")

    @cocoa(deps=[Config])
    class Database:
        @on_start
        async def connect(self) -> None:
            await asyncio.sleep(0)
            events.append("db.connect")

        @on_stop
        async def disconnect(self) -> None:
            await asyncio.sleep(0)
            events.append("db.disconnect")

    @cocoa(deps=[Database])
    class Repository:
        @on_start
        async def warm(self) -> None:
            await asyncio.sleep(0)
            events.append("repo.warm")

        @on_stop
        async def flush(self) -> None:
            await asyncio.sleep(0)
            events.append("repo.flush")

    @cocoa(deps=[Repository])
    class Service:
        @on_start
        async def start(self) -> None:
            await asyncio.sleep(0)
            events.append("service.start")

        @on_stop
        async def stop(self) -> None:
            await asyncio.sleep(0)
            events.append("service.stop")

    async with Canary(Service) as canary:
        assert canary.state is LifecycleState.STARTED
        # 全图共享同一批单例，依赖在异步钩子前注入。
        assert canary[Service].repository is canary[Repository]
        assert canary[Repository].database is canary[Database]
        assert canary[Database].config is canary[Config]

    assert events == [
        "config.load",
        "db.connect",
        "repo.warm",
        "service.start",
        "service.stop",
        "repo.flush",
        "db.disconnect",
    ]
