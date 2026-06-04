"""Unit tests for common.types module."""

import pytest

from canary_framework.common.types import (
    LifecycleHook,
    ModuleMeta,
    RouterMeta,
    ServiceEntry,
    ServiceMeta,
)


@pytest.mark.unit
class TestLifecycleHook:
    """Tests for LifecycleHook enum."""

    def test_enum_values(self) -> None:
        """Test that enum has correct values."""
        assert LifecycleHook.AFTER_CONFIG.value == "after_config"
        assert LifecycleHook.AFTER_INIT.value == "after_init"
        assert LifecycleHook.BEFORE_STARTUP.value == "before_startup"
        assert LifecycleHook.BEFORE_SHUTDOWN.value == "before_shutdown"

    def test_enum_iteration(self) -> None:
        """Test enum iteration."""
        values = list(LifecycleHook)
        assert len(values) == 4


@pytest.mark.unit
class TestServiceMeta:
    """Tests for ServiceMeta dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        meta = ServiceMeta(name="test")
        assert meta.name == "test"

    def test_custom_values(self) -> None:
        """Test custom values are set correctly."""
        meta = ServiceMeta(name="custom")
        assert meta.name == "custom"


@pytest.mark.unit
class TestModuleMeta:
    """Tests for ModuleMeta dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        meta = ModuleMeta(name="test")
        assert meta.name == "test"
        assert meta.services == []

    def test_custom_values(self) -> None:
        """Test custom values are set correctly."""

        class Service:
            pass

        meta = ModuleMeta(name="custom", services=[Service])
        assert meta.name == "custom"
        assert meta.services == [Service]


@pytest.mark.unit
class TestRouterMeta:
    """Tests for RouterMeta dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        meta = RouterMeta(name="test")
        assert meta.name == "test"
        assert meta.prefix == ""
        assert meta.tags == []
        assert meta.routes == []

    def test_custom_values(self) -> None:
        """Test custom values are set correctly."""

        def route_fn() -> None:
            pass

        meta = RouterMeta(name="custom", prefix="/api", tags=["test"], routes=[route_fn])
        assert meta.name == "custom"
        assert meta.prefix == "/api"
        assert meta.tags == ["test"]
        assert meta.routes == [route_fn]


@pytest.mark.unit
class TestServiceEntry:
    """Tests for ServiceEntry dataclass."""

    def test_default_values(self) -> None:

        class MyClass:
            pass

        entry = ServiceEntry(cls=MyClass, name="test")
        assert entry.cls == MyClass
        assert entry.name == "test"
        assert entry.instance is None

    def test_custom_values(self) -> None:

        class MyClass:
            pass

        instance = MyClass()
        entry = ServiceEntry(cls=MyClass, name="test", instance=instance)
        assert entry.cls == MyClass
        assert entry.name == "test"
        assert entry.instance is instance
