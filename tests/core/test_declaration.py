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


def test_a_dependency_overridden_by_name_is_replaced() -> None:
    """依赖与钩子一样按属性名解析：子类换掉一条 ``dep()``，基类那条边就不在了。"""

    class Default(Canary): ...

    class Replacement(Default): ...

    class Other(Canary): ...

    class Base(Canary):
        thing = dep(Default)
        other = dep(Other)

    class Derived(Base):
        thing = dep(Replacement)

    class Dropped(Base):
        thing = None  # type: ignore[assignment]  # 换成别的东西：不再是依赖

    class Added(Derived):
        extra = dep(Default)

    assert deps_of(Base) == (Default, Other)
    assert deps_of(Derived) == (Replacement, Other), "顺序仍按首次声明的位置"
    assert deps_of(Dropped) == (Other,)
    assert deps_of(Added) == (Replacement, Other, Default)


async def test_the_overridden_dependency_is_never_built() -> None:
    built: list[str] = []

    class Default(Canary):
        def __init__(self) -> None:
            built.append(type(self).__name__)

    class Replacement(Default): ...

    class Base(Canary):
        thing = dep(Default)

    class Derived(Base):
        thing = dep(Replacement)

    async with Derived() as unit:
        assert type(unit.thing) is Replacement
    assert built == ["Replacement"]
