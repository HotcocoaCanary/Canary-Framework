"""Functional tests for asynchronous router applications."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

pytestmark = pytest.mark.functional


async def test_async_lifecycle_hooks() -> None:
    events: list[str] = []

    @service()
    class AsyncService(ServiceBase):
        async def on_startup(self) -> None:
            await asyncio.sleep(0.01)
            events.append("async-startup")

    @module(children=(AsyncService,))
    class MyModule(ModuleBase):
        pass

    app = MyModule()
    await app.init()
    await app.startup()
    assert events == ["async-startup"]


async def test_concurrent_requests() -> None:
    @service()
    class CounterService(ServiceBase):
        def __init__(self) -> None:
            super().__init__()
            self.count = 0

        async def increment(self) -> int:
            await asyncio.sleep(0.01)
            self.count += 1
            return self.count

    @router()
    class CounterRouter(RouterBase):
        counter_service: CounterService

        @get("/increment")
        async def increment(self) -> dict[str, int]:
            return {"count": await self.counter_service.increment()}

    @module(children=(CounterRouter,))
    class CounterApp(ModuleBase):
        pass

    app = CounterApp()
    await app.init()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.get("/increment") for _ in range(5)))
    assert all(response.status_code == 200 for response in responses)
    assert app.direct_children[0].counter_service.count == 5  # type: ignore[attr-defined]


async def test_long_running_operations() -> None:
    @service()
    class LongTaskService(ServiceBase):
        async def do_work(self, seconds: float) -> dict[str, str | float]:
            await asyncio.sleep(seconds)
            return {"status": "done", "duration": seconds}

    @router()
    class TaskRouter(RouterBase):
        long_task_service: LongTaskService

        @get("/task?seconds={seconds}")
        async def run_task(self, seconds: float) -> dict[str, str | float]:
            return await self.long_task_service.do_work(seconds)

    @module(children=(TaskRouter,))
    class TaskApp(ModuleBase):
        pass

    app = TaskApp()
    await app.init()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=5.0
    ) as client:
        response = await client.get("/task?seconds=0.1")
    assert response.status_code == 200
    assert response.json() == {"status": "done", "duration": 0.1}
