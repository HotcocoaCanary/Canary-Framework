"""Integration tests for lifecycle."""

import pytest

from canary_framework import (
    module,
    service,
)
from canary_framework.core.module import ModuleBase
from canary_framework.core.service import ServiceBase


@pytest.mark.integration
class TestLifecycle:
    """Integration tests for lifecycle."""

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_execution_order(self) -> None:
        """Test that lifecycle hooks execute in order."""

        events: list[str] = []

        @service()
        class MyService(ServiceBase):
            def on_init(self) -> None:
                events.append("service-init")

            async def startup(self) -> None:
                await super().startup()
                events.append("service-startup")

            async def shutdown(self) -> None:
                await super().shutdown()
                events.append("service-shutdown")

        @module(services=[MyService])
        class MyModule(ModuleBase):
            def on_init(self) -> None:
                events.append("module-init")

            async def startup(self) -> None:
                await super().startup()
                events.append("module-startup")

            async def shutdown(self) -> None:
                await super().shutdown()
                events.append("module-shutdown")

        app = MyModule()
        app.init()
        await app.startup()
        await app.shutdown()

        # Check that all hooks were called
        assert len(events) == 4
        assert "service-startup" in events
        assert "service-shutdown" in events
        assert "module-startup" in events
        assert "module-shutdown" in events

    @pytest.mark.asyncio
    async def test_lifecycle_with_multiple_services(self) -> None:
        """Test lifecycle with multiple services."""

        startup_order: list[str] = []
        shutdown_order: list[str] = []

        @service()
        class Service1(ServiceBase):
            async def startup(self) -> None:
                await super().startup()
                startup_order.append("Service1")

            async def shutdown(self) -> None:
                await super().shutdown()
                shutdown_order.append("Service1")

        @service()
        class Service2(ServiceBase):
            async def startup(self) -> None:
                await super().startup()
                startup_order.append("Service2")

            async def shutdown(self) -> None:
                await super().shutdown()
                shutdown_order.append("Service2")

        @module(services=[Service1, Service2])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()
        await app.startup()
        await app.shutdown()

        assert len(startup_order) == 2
        assert len(shutdown_order) == 2
        # Shutdown order should be reverse of startup order
        assert shutdown_order == startup_order[::-1]
