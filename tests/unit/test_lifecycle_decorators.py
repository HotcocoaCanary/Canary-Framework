"""Unit tests for decorators.lifecycle module."""

import pytest

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook
from canary_framework.decorators.lifecycle import (
    after_config,
    after_init,
    before_shutdown,
    before_startup,
)


@pytest.mark.unit
class TestLifecycleDecorators:
    """Tests for lifecycle decorators."""

    def test_after_config_decorator(self) -> None:
        """Test @after_config decorator."""

        @after_config
        def my_hook() -> None:
            pass

        assert getattr(my_hook, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], False) is True

    def test_after_init_decorator(self) -> None:
        """Test @after_init decorator."""

        @after_init
        def my_hook() -> None:
            pass

        assert getattr(my_hook, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_INIT], False) is True

    def test_before_startup_decorator(self) -> None:
        """Test @before_startup decorator."""

        @before_startup
        def my_hook() -> None:
            pass

        assert getattr(my_hook, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_STARTUP], False) is True

    def test_before_shutdown_decorator(self) -> None:
        """Test @before_shutdown decorator."""

        @before_shutdown
        def my_hook() -> None:
            pass

        assert getattr(my_hook, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_SHUTDOWN], False) is True

    def test_decorator_preserves_function(self) -> None:
        """Test decorator preserves function."""

        def original() -> str:
            return "test"

        decorated = after_config(original)
        assert decorated() == "test"
