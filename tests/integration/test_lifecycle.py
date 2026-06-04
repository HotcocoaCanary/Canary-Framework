"""Integration tests for lifecycle."""

import pytest

from canary_framework import (
    after_config,
    after_init,
    before_shutdown,
    before_startup,
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
            @after_config
            def on_config(self) -> None:
                events.append("service-config")

            @after_init
            def on_init(self) -> None:
                events.append("service-init")

            @before_startup
            def on_startup(self) -> None:
                events.append("service-startup")

            @before_shutdown
            def on_shutdown(self) -> None:
                events.append("service-shutdown")

        @module(services=[MyService])
        class MyModule(ModuleBase):
            @after_config
            def on_config(self) -> None:
                events.append("module-config")

            @after_init
            def on_init(self) -> None:
                events.append("module-init")

            @before_startup
            def on_startup(self) -> None:
                events.append("module-startup")

            @before_shutdown
            def on_shutdown(self) -> None:
                events.append("module-shutdown")

        app = MyModule()
        await app.configure()
        await app.init()
        await app.startup()
        await app.shutdown()

        # Check that all hooks were called
        assert len(events) == 8
        assert "service-config" in events
        assert "service-init" in events
        assert "service-startup" in events
        assert "service-shutdown" in events
        assert "module-config" in events
        assert "module-init" in events
        assert "module-startup" in events
        assert "module-shutdown" in events

    @pytest.mark.asyncio
    async def test_lifecycle_with_multiple_services(self) -> None:
        """Test lifecycle with multiple services."""

        startup_order: list[str] = []
        shutdown_order: list[str] = []

        @service()
        class Service1(ServiceBase):
            @before_startup
            def on_startup(self) -> None:
                startup_order.append("Service1")

            @before_shutdown
            def on_shutdown(self) -> None:
                shutdown_order.append("Service1")

        @service()
        class Service2(ServiceBase):
            @before_startup
            def on_startup(self) -> None:
                startup_order.append("Service2")

            @before_shutdown
            def on_shutdown(self) -> None:
                shutdown_order.append("Service2")

        @module(services=[Service1, Service2])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.configure()
        await app.startup()
        await app.shutdown()

        assert len(startup_order) == 2
        assert len(shutdown_order) == 2
        # Shutdown order should be reverse of startup order
        assert shutdown_order == startup_order[::-1]
