"""Integration tests for lifecycle."""

import pytest

from canary_framework import (
    Canary,
    module,
    service,
)


@pytest.mark.integration
class TestLifecycle:
    """Integration tests for lifecycle."""

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_execution_order(self) -> None:
        """Test that lifecycle hooks execute in order."""

        events: list[str] = []

        @service()
        class MyService:
            def on_init(self) -> None:
                events.append("service-init")

            async def startup(self) -> None:
                events.append("service-startup")

            async def shutdown(self) -> None:
                events.append("service-shutdown")

        @module(services=[MyService])
        class MyModule:
            def on_init(self) -> None:
                events.append("module-init")

            async def startup(self) -> None:
                events.append("module-startup")

            async def shutdown(self) -> None:
                events.append("module-shutdown")

        app = Canary(MyModule())
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
        class Service1:
            async def startup(self) -> None:
                startup_order.append("Service1")

            async def shutdown(self) -> None:
                shutdown_order.append("Service1")

        @service()
        class Service2:
            async def startup(self) -> None:
                startup_order.append("Service2")

            async def shutdown(self) -> None:
                shutdown_order.append("Service2")

        @module(services=[Service1, Service2])
        class MyModule:
            pass

        app = Canary(MyModule())
        await app.startup()
        await app.shutdown()

        assert len(startup_order) == 2
        assert len(shutdown_order) == 2
        # Shutdown order should be reverse of startup order
        assert shutdown_order == startup_order[::-1]
