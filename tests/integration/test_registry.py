"""Tests for :mod:`canary_framework.core.container.registry`."""

from __future__ import annotations

import pytest

from canary_framework.common._types import ModuleMeta, ServiceEntry
from canary_framework.common.exceptions import ServiceNotFoundError
from canary_framework.core.container.registry import Registry
from canary_framework.core.decorators.service import service


@pytest.mark.integration
class TestServiceEntry:
    """Verify ServiceEntry dataclass construction and defaults."""

    def test_default_values(self) -> None:
        entry = ServiceEntry(cls=str, instance="hello", name="test")
        assert entry.cls is str
        assert entry.instance == "hello"
        assert entry.name == "test"
        assert entry.deps == []
        assert entry.sub_services == []
        assert entry.dep_names == []
        assert entry.parent_entry is None
        assert entry._hooks is None

    def test_slots_no_dict(self) -> None:
        """slots=True means no __dict__."""
        entry = ServiceEntry(cls=str, instance="hello", name="test")
        with pytest.raises(AttributeError):
            _ = entry.__dict__


@pytest.mark.integration
class TestRegistry:
    """Integration tests for the Registry container."""

    def test_register_and_lookup_by_name(self) -> None:
        @service("db")
        class DBService:
            pass

        reg = Registry()
        reg.register(DBService)
        entry = reg.get_by_name("db")
        assert entry.name == "db"
        assert entry.cls is DBService

    def test_register_and_lookup_by_class(self) -> None:
        @service("db")
        class DBService:
            pass

        reg = Registry()
        reg.register(DBService)
        entry = reg.get_by_class(DBService)
        assert entry.name == "db"

    def test_register_idempotent(self) -> None:
        @service("db")
        class DBService:
            pass

        reg = Registry()
        reg.register(DBService)
        reg.register(DBService)
        assert len(reg) == 1

    def test_duplicate_name_raises(self) -> None:
        @service("db")
        class DB1:
            pass

        @service("db")
        class DB2:
            pass

        reg = Registry()
        reg.register(DB1)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(DB2)

    def test_get_by_name_missing_raises(self) -> None:
        reg = Registry()
        with pytest.raises(ServiceNotFoundError, match="not registered"):
            reg.get_by_name("nonexistent")

    def test_get_by_class_missing_raises(self) -> None:
        reg = Registry()

        class NotRegistered:
            pass

        with pytest.raises(ServiceNotFoundError, match="NotRegistered"):
            reg.get_by_class(NotRegistered)

    def test_get_instance(self) -> None:
        @service("db")
        class DBService:
            pass

        reg = Registry()
        reg.register(DBService)
        inst = reg.get_instance(DBService)
        assert isinstance(inst, DBService)

    def test_has(self) -> None:
        @service("x")
        class X:
            pass

        reg = Registry()
        reg.register(X)
        assert reg.has(X) is True
        assert reg.has(str) is False

    def test_contains(self) -> None:
        @service("x")
        class X:
            pass

        reg = Registry()
        reg.register(X)
        assert X in reg
        assert str not in reg

    def test_all_entries_and_names(self) -> None:
        @service("a")
        class A:
            pass

        @service("b")
        class B:
            pass

        reg = Registry()
        reg.register(A)
        reg.register(B)

        assert len(reg) == 2
        assert set(reg.names()) == {"a", "b"}
        assert len(reg.all_entries()) == 2

    def test_iteration(self) -> None:
        @service("x")
        class X:
            pass

        reg = Registry()
        reg.register(X)
        entries = list(reg)
        assert len(entries) == 1
        assert entries[0].name == "x"

    def test_register_module_with_meta(self) -> None:
        @service("child")
        class Child:
            pass

        class Root:
            pass

        reg = Registry()
        meta = ModuleMeta(name="root", services=[Child])
        reg.register(Root, meta=meta)
        entry = reg.get_by_class(Root)
        assert entry.sub_services == [Child]
