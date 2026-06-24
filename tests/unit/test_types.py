"""Unit tests for common.types module."""

import pytest

from canary_framework.common.types import (
    ModuleMeta,
    ServiceEntry,
    ServiceMeta,
)


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
