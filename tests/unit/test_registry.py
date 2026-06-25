"""Unit tests for engine.registry module."""

import pytest

from canary_framework.common.errors import ServiceNotFoundError
from canary_framework.common.types import ServiceMeta
from canary_framework.core.registry import Registry


@pytest.mark.unit
class TestRegistry:
    """Tests for Registry class."""

    def test_register_and_get_by_name(self) -> None:
        """Test registering a service and getting it by name."""
        reg = Registry()

        class TestService:
            pass

        meta = ServiceMeta(name="test_service")

        reg.register(TestService, meta=meta)

        entry = reg.get_by_name("test_service")
        assert entry.cls is TestService
        assert entry.name == "test_service"

    def test_register_and_get_by_class(self) -> None:
        """Test registering a service and getting it by class."""
        reg = Registry()

        class TestService:
            pass

        meta = ServiceMeta(name="test_service")

        reg.register(TestService, meta=meta)

        entry = reg.get_by_class(TestService)
        assert entry.cls is TestService
        assert entry.name == "test_service"

    def test_get_by_name_not_found(self) -> None:
        """Test getting non-existent service by name raises error."""
        reg = Registry()

        with pytest.raises(ServiceNotFoundError):
            reg.get_by_name("nonexistent")

    def test_get_by_class_not_found(self) -> None:
        """Test getting non-existent service by class raises error."""
        reg = Registry()

        class NonExistent:
            pass

        with pytest.raises(ServiceNotFoundError):
            reg.get_by_class(NonExistent)

    def test_has_service(self) -> None:
        """Test has method checks if service is registered."""
        reg = Registry()

        class TestService:
            pass

        meta = ServiceMeta(name="test_service")

        assert reg.has(TestService) is False
        reg.register(TestService, meta=meta)
        assert reg.has(TestService) is True

    def test_duplicate_register_duplicate_name_raises(self) -> None:
        """Test registering same name twice raises ValueError."""
        reg = Registry()

        class Service1:
            pass

        class Service2:
            pass

        meta1 = ServiceMeta(name="same_name")
        meta2 = ServiceMeta(name="same_name")

        reg.register(Service1, meta=meta1)
        with pytest.raises(ValueError):
            reg.register(Service2, meta=meta2)

    def test_idempotent_register(self) -> None:
        """Test registering same class twice does nothing."""
        reg = Registry()

        class TestService:
            pass

        meta = ServiceMeta(name="test_service")

        reg.register(TestService, meta=meta)
        reg.register(TestService, meta=meta)  # Should not raise
        assert len(reg.all_entries()) == 1

    def test_all_entries(self) -> None:
        """Test all_entries returns all entries."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        reg.register(A, meta=ServiceMeta(name="a"))
        reg.register(B, meta=ServiceMeta(name="b"))

        entries = reg.all_entries()
        assert len(entries) == 2

    def test_names(self) -> None:
        """Test names returns all names."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        reg.register(A, meta=ServiceMeta(name="a"))
        reg.register(B, meta=ServiceMeta(name="b"))

        names = reg.names()
        assert set(names) == {"a", "b"}

    def test_len(self) -> None:
        """Test all_entries returns correct count."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        assert len(reg.all_entries()) == 0
        reg.register(A, meta=ServiceMeta(name="a"))
        assert len(reg.all_entries()) == 1
        reg.register(B, meta=ServiceMeta(name="b"))
        assert len(reg.all_entries()) == 2

    def test_contains(self) -> None:
        """Test has works correctly."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        reg.register(A, meta=ServiceMeta(name="a"))

        assert reg.has(A) is True
        assert reg.has(B) is False

    def test_parent_registry_lookup(self) -> None:
        """Test lookup in parent registry."""
        parent = Registry()
        child = Registry(parent=parent)

        class ParentService:
            pass

        parent.register(ParentService, meta=ServiceMeta(name="parent_service"))

        assert child.has(ParentService) is True
        entry = child.get_by_class(ParentService)
        assert entry.cls is ParentService
