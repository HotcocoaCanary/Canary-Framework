"""作用域：一个类型一个实例、无参构造、作用域归属。"""

from __future__ import annotations

import pytest

from canary_framework import (
    Canary,
    ConstructionError,
    dep,
    enter,
    init,
    scope_of,
)

pytestmark = pytest.mark.unit


class Shared(Canary): ...


async def test_one_instance_per_type_across_the_whole_graph() -> None:
    class Left(Canary):
        shared = dep(Shared)

    class Right(Canary):
        shared = dep(Shared)

    class Root(Canary):
        left = dep(Left)
        right = dep(Right)

    root = Root()
    await enter(root, init)
    assert root.left.shared is root.right.shared


async def test_a_unit_that_needs_constructor_arguments_is_refused_with_an_actionable_error() -> (
    None
):
    class NeedsArgs(Canary):
        def __init__(self, dsn: str) -> None:
            self.dsn = dsn

    class Root(Canary):
        needs = dep(NeedsArgs)

    with pytest.raises(ConstructionError, match="Declare what it needs with dep"):
        await enter(Root(), init)


async def test_a_type_error_raised_by_the_constructor_itself_propagates_unchanged() -> None:
    class Angry(Canary):
        def __init__(self) -> None:
            raise TypeError("my own problem")

    class Root(Canary):
        angry = dep(Angry)

    with pytest.raises(TypeError, match="my own problem"):
        await enter(Root(), init)


def test_a_root_gets_one_scope_and_keeps_it() -> None:
    class Root(Canary): ...

    root = Root()
    assert scope_of(root) is scope_of(root)


def test_two_roots_constructed_separately_do_not_share_a_scope() -> None:
    class Root(Canary): ...

    assert scope_of(Root()) is not scope_of(Root())
