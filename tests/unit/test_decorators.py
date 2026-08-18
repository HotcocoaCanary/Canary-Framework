"""Unit tests for the marker decorators."""

import pytest

from canary_framework import cocoa, on_init, on_start, on_stop
from canary_framework.core.decorator import (
    deps_of,
    init_hooks,
    is_cocoa,
    start_hooks,
    stop_hooks,
)

pytestmark = pytest.mark.unit


def test_cocoa_marks_a_class() -> None:
    @cocoa
    class Database:
        pass

    assert is_cocoa(Database)


def test_cocoa_is_dual_use() -> None:
    @cocoa
    class A:
        pass

    @cocoa(deps=[A])
    class B:
        pass

    assert deps_of(A) == []
    assert deps_of(B) == [A]


def test_cocoa_preserves_class_identity() -> None:
    @cocoa
    class Service:
        def greet(self) -> str:
            return "hi"

    assert Service.__name__ == "Service"
    assert Service().greet() == "hi"


def test_hook_markers_are_collected() -> None:
    @cocoa
    class Service:
        @on_init
        def setup(self) -> None: ...

        @on_start
        def run(self) -> None: ...

        @on_stop
        def teardown(self) -> None: ...

    inst = Service()
    assert [f.__name__ for f in init_hooks(inst)] == ["setup"]
    assert [f.__name__ for f in start_hooks(inst)] == ["run"]
    assert [f.__name__ for f in stop_hooks(inst)] == ["teardown"]


def test_hooks_are_stackable_in_definition_order() -> None:
    @cocoa
    class Service:
        @on_start
        def first(self) -> None: ...

        @on_start
        def second(self) -> None: ...

    assert [f.__name__ for f in start_hooks(Service())] == ["first", "second"]


def test_hooks_run_mixins_before_the_class() -> None:
    class Mixin:
        @on_start
        def mixin_hook(self) -> None: ...

    @cocoa
    class Service(Mixin):
        @on_start
        def own_hook(self) -> None: ...

    assert [f.__name__ for f in start_hooks(Service())] == ["mixin_hook", "own_hook"]


def test_hooks_accumulate_across_same_named_mixins() -> None:
    calls: list[str] = []

    class AMixin:
        @on_start
        def start(self) -> None:
            calls.append("a")

    class BMixin:
        @on_start
        def start(self) -> None:
            calls.append("b")

    @cocoa
    class Service(AMixin, BMixin):
        pass

    hooks = start_hooks(Service())
    assert [f.__name__ for f in hooks] == ["start", "start"]
    for hook in hooks:
        hook()
    assert calls == ["b", "a"]
