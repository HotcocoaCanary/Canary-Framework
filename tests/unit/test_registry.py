"""Unit tests for local and inherited service registry behavior."""

import pytest

from canary_framework.common.errors import DependencyInjectionError, ServiceNotFoundError
from canary_framework.engine.registry import Registry


class Shared:
    pass


@pytest.mark.unit
def test_registry_distinguishes_local_from_inherited() -> None:
    parent = Registry()
    parent.register(Shared, "Shared")
    child = Registry(parent=parent)

    assert child.has(Shared)
    assert not child.has_local(Shared)
    assert tuple(entry.cls for entry in child.local_entries()) == ()


@pytest.mark.unit
def test_local_entries_and_instances_preserve_registration_order() -> None:
    class First:
        pass

    class Second:
        pass

    registry = Registry()
    registry.register(First, "first")
    registry.register(Second, "second")
    first = First()
    registry.get_by_class(First).instance = first

    assert tuple(entry.cls for entry in registry.local_entries()) == (First, Second)
    assert registry.local_instances() == (first,)


@pytest.mark.unit
def test_registry_rejects_legacy_meta_keyword() -> None:
    registry = Registry()

    with pytest.raises(TypeError, match="unexpected keyword argument 'meta'"):
        registry.register(Shared, meta=object())  # type: ignore[call-arg]


@pytest.mark.unit
def test_get_returns_inherited_instance() -> None:
    parent = Registry()
    parent.register(Shared, "Shared")
    instance = Shared()
    parent.get_by_class(Shared).instance = instance

    assert Registry(parent=parent).get(Shared) is instance


@pytest.mark.unit
def test_get_rejects_uninstantiated_entry() -> None:
    registry = Registry()
    registry.register(Shared, "Shared")

    with pytest.raises(DependencyInjectionError, match=r"Shared.*instance"):
        registry.get(Shared)


@pytest.mark.unit
def test_duplicate_name_and_missing_lookups_raise() -> None:
    class Other:
        pass

    registry = Registry()
    registry.register(Shared, "same")

    with pytest.raises(ValueError, match="same"):
        registry.register(Other, "same")
    with pytest.raises(ServiceNotFoundError):
        registry.get_by_class(Other)
    with pytest.raises(ServiceNotFoundError):
        registry.get_by_name("missing")
