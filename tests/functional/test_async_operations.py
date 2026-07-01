"""Functional tests for async operations."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from canary_framework import before_startup, module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestAsyncOperations:
    """Functional tests for async operations."""

    @pytest.mark.asyncio
    async def test_async_lifecycle_hooks(self) -> None:
        """Test async lifecycle hooks."""

        events: list[str] = []

        @service()
        class AsyncService(ServiceBase):
            async def async_init(self) -> None:
                await asyncio.sleep(0.01)
                events.append("async-init")

            @before_startup
            async def async_startup(self) -> None:
                await asyncio.sleep(0.01)
                events.append("async-startup")

        @module(services=[AsyncService])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()
        await app.startup()

        assert "async-startup" in events

    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Test concurrent requests."""

        @service()
        class CounterService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.count = 0

            async def increment(self) -> int:
                # Simulate async work
                await asyncio.sleep(0.01)
                self.count += 1
                return self.count

        @service()
        class CounterRouter(ServiceBase):
            router = Router()
            counter_service: CounterService

            @router.get("/increment")
            async def increment(self) -> dict[str, int]:
                result = await self.counter_service.increment()
                return {"count": result}

        @module(services=[CounterRouter])
        class CounterApp(ModuleBase):
            pass

        app = CounterApp()
        app.init()

        # Make concurrent requests
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            requests = [client.get("/increment") for _ in range(5)]
            responses = await asyncio.gather(*requests)

            # All should succeed
            for response in responses:
                assert response.status_code == 200

            # Count should be 5
            assert app.CounterRouter.counter_service.count == 5  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_long_running_operations(self) -> None:
        """Test long running operations."""

        @service()
        class LongTaskService(ServiceBase):
            async def do_work(self, seconds: float) -> dict[str, str | float]:
                await asyncio.sleep(seconds)
                return {"status": "done", "duration": seconds}

        @service()
        class TaskRouter(ServiceBase):
            router = Router()
            long_task_service: LongTaskService

            @router.get("/task?seconds={seconds}")
            async def run_task(self, seconds: float) -> dict[str, str | float]:
                return await self.long_task_service.do_work(seconds)

        @module(services=[TaskRouter])
        class TaskApp(ModuleBase):
            pass

        app = TaskApp()
        app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=5.0,
        ) as client:
            response = await client.get("/task?seconds=0.1")
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "done"
            assert result["duration"] == 0.1
