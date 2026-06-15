"""Unit tests for lifecycle decorators."""

import pytest

from canary_framework import before_shutdown, before_startup


@pytest.mark.unit
class TestLifecycleDecorators:
    """Tests for lifecycle decorators."""

    def test_before_startup_decorator(self) -> None:
        """Test @before_startup decorator."""
        events: list[str] = []

        @before_startup
        def my_hook() -> None:
            events.append("startup")

        assert hasattr(my_hook, "__cf_before_startup__")
        my_hook()
        assert events == ["startup"]

    def test_before_shutdown_decorator(self) -> None:
        """Test @before_shutdown decorator."""
        events: list[str] = []

        @before_shutdown
        def my_hook() -> None:
            events.append("shutdown")

        assert hasattr(my_hook, "__cf_before_shutdown__")
        my_hook()
        assert events == ["shutdown"]
