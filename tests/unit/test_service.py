"""Unit tests for core.service module."""

import pytest

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook
from canary_framework.common.config import CanaryConfig
from canary_framework.common.errors import LifecycleHookError
from canary_framework.core.service import ServiceBase


@pytest.mark.unit
class TestServiceBase:
    """Tests for ServiceBase class."""

    def test_initialization(self) -> None:
        """Test initialization sets up attributes."""
        service = ServiceBase()
        assert service._cf_hooks is None
        assert service.config is None

    @pytest.mark.asyncio
    async def test_configure_sets_config(self) -> None:
        """Test configure sets the config."""
        service = ServiceBase()
        config = CanaryConfig(host="0.0.0.0", port=3000)
        await service.configure(config)
        assert service.config == config

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_called(self) -> None:
        """Test that lifecycle hooks are called."""

        class MyService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.after_config_called = False
                self.after_init_called = False
                self.before_startup_called = False
                self.before_shutdown_called = False

            def after_config(self) -> None:
                self.after_config_called = True

            def after_init(self) -> None:
                self.after_init_called = True

            def before_startup(self) -> None:
                self.before_startup_called = True

            def before_shutdown(self) -> None:
                self.before_shutdown_called = True

        setattr(MyService.after_config, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)
        setattr(MyService.after_init, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_INIT], True)
        setattr(MyService.before_startup, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_STARTUP], True)
        setattr(MyService.before_shutdown, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_SHUTDOWN], True)

        service = MyService()

        await service.configure(None)
        assert service.after_config_called

        await service.init()
        assert service.after_init_called

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
                self.after_config_called = False

            async def after_config(self) -> None:
                self.after_config_called = True

        setattr(MyService.after_config, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)

        service = MyService()
        await service.configure(None)
        assert service.after_config_called

    @pytest.mark.asyncio
    async def test_hook_error_wrapped(self) -> None:
        """Test that hook errors are wrapped in LifecycleHookError."""

        class MyService(ServiceBase):
            def after_config(self) -> None:
                raise ValueError("Test error")

        setattr(MyService.after_config, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)

        service = MyService()

        with pytest.raises(LifecycleHookError):
            await service.configure(None)
