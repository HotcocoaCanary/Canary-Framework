"""阶段标记与钩子查找：叠加、混入、覆盖、自定义阶段。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, Phase, advance, init, start

pytestmark = pytest.mark.unit


async def test_one_class_may_have_several_hooks_in_one_phase_in_definition_order() -> None:
    seen: list[str] = []

    class Many(Canary):
        @init
        def first(self) -> None:
            seen.append("first")

        @init
        def second(self) -> None:
            seen.append("second")

    await advance(Many(), init)
    assert seen == ["first", "second"]


async def test_one_method_may_belong_to_several_phases() -> None:
    seen: list[str] = []

    class Both(Canary):
        @init
        @start
        def touch(self) -> None:
            seen.append("touch")

    unit = Both()
    await advance(unit, init)
    await advance(unit, start)
    assert seen == ["touch", "touch"]


async def test_a_mixins_hook_runs_before_the_units_own() -> None:
    seen: list[str] = []

    class Audited:
        @init
        def audit(self) -> None:
            seen.append("mixin")

    class Unit(Audited, Canary):
        @init
        def own(self) -> None:
            seen.append("own")

    await advance(Unit(), init)
    assert seen == ["mixin", "own"]


async def test_overriding_a_hook_replaces_it_the_way_a_plain_method_would() -> None:
    seen: list[str] = []

    class Base(Canary):
        @init
        def prepare(self) -> None:
            seen.append("base")

    class Overriding(Base):
        @init
        def prepare(self) -> None:
            seen.append("override")

    class Inheriting(Base): ...

    await advance(Overriding(), init)
    await advance(Inheriting(), init)
    assert seen == ["override", "base"]


async def test_an_override_that_drops_the_marker_drops_the_hook() -> None:
    seen: list[str] = []

    class Base(Canary):
        @init
        def prepare(self) -> None:
            seen.append("base")

    class Silent(Base):
        def prepare(self) -> None:
            seen.append("silent")

    await advance(Silent(), init)
    assert seen == []


async def test_a_phase_the_framework_does_not_ship_works_the_same_way() -> None:
    migrate = Phase("migrate")
    seen: list[str] = []

    class Schema(Canary):
        @migrate
        async def apply(self) -> None:
            seen.append("schema")

    await advance(Schema(), migrate)
    assert seen == ["schema"]
