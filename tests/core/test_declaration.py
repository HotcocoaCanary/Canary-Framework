"""声明期：dep(...)、deps_of、以及继承 Canary 带来的东西。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, DeclarationError, LifecycleError, dep, deps_of

pytestmark = pytest.mark.unit


class Alpha(Canary): ...


class Beta(Canary): ...


def test_dep_refuses_a_class_that_is_not_a_unit() -> None:
    class Plain: ...

    with pytest.raises(DeclarationError, match="not a Canary subclass"):
        dep(Plain)  # type: ignore[type-var]


def test_the_attribute_name_is_the_users_choice_not_the_class_name() -> None:
    class Uses(Canary):
        anything = dep(Alpha)

    assert deps_of(Uses) == (Alpha,)
    assert isinstance(Uses.__dict__["anything"].cls, type)


def test_deps_are_collected_base_first_in_definition_order() -> None:
    class Base(Canary):
        a = dep(Alpha)

    class Derived(Base):
        b = dep(Beta)

    assert deps_of(Derived) == (Alpha, Beta)


def test_two_attributes_naming_one_type_count_once() -> None:
    class Twice(Canary):
        first = dep(Alpha)
        second = dep(Alpha)

    assert deps_of(Twice) == (Alpha,)


def test_a_dependency_is_unavailable_before_the_lifecycle_begins() -> None:
    class Early(Canary):
        a = dep(Alpha)

    with pytest.raises(LifecycleError, match="before the lifecycle begins"):
        _ = Early().a


def test_a_substitute_is_a_unit_just_by_subclassing_the_one_it_replaces() -> None:
    class Stub(Alpha): ...

    assert issubclass(Stub, Canary)
    assert dep(Stub) is not None


def test_reading_a_dep_off_the_class_gives_back_the_declaration() -> None:
    class Uses(Canary):
        anything = dep(Alpha)

    assert Uses.anything.cls is Alpha  # type: ignore[attr-defined]
