"""Unit tests for core.service module."""

import pytest

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook
from canary_framework.core.service import ServiceBase


@pytest.mark.unit
class TestServiceBase:
    """Tests for ServiceBase class."""

    def test_initialization(self) -> None:
        """Test initialization sets up attributes."""
        service = ServiceBase()
        assert service._cf_hooks is None

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_called(self) -> None:
        """Test that lifecycle hooks are called."""

        class MyService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.before_startup_called = False
                self.before_shutdown_called = False

            def before_startup(self) -> None:
                self.before_startup_called = True

            def before_shutdown(self) -> None:
                self.before_shutdown_called = True

        setattr(MyService.before_startup, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_STARTUP], True)
        setattr(MyService.before_shutdown, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_SHUTDOWN], True)

        service = MyService()

        service.init()

        await service.startup()
        assert service.before_startup_called

        await service.shutdown()
        assert service.before_shutdown_called

    @pytest.mark.asyncio
    async def test_async_hook_called(self) -> None:
        """Test that async hooks are awaited."""

        class MyService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()

        service = MyService()
        service.init()

    @pytest.mark.asyncio
    async def test_init_no_effect(self) -> None:
        """Test that init() runs without errors when no hooks are registered."""

        class MyService(ServiceBase):
            pass

        service = MyService()
        service.init()  # should not raise
