"""Tests for :mod:`canary_framework.core.conductor.sorter`."""

from __future__ import annotations

import pytest

from canary_framework.common.exceptions import CircularDependencyError
from canary_framework.core.algorithms.sorter import topological_sort
from canary_framework.core.container.registry import Registry
from canary_framework.core.decorators.service import service


class TestTopologicalSort:
    """Verify Kahn-based topological sorting."""

    def test_single_node(self) -> None:
        @service("a")
        class A:
            pass

        reg = Registry()
        reg.register(A)
        order = topological_sort(reg)
        assert order == ["a"]

    def test_linear_chain(self) -> None:
        @service("a")
        class A:
            pass

        @service("b", deps=[A])
        class B:
            pass

        @service("c", deps=[B])
        class C:
            pass

        reg = Registry()
        reg.register(A)
        reg.register(B)
        reg.register(C)
        order = topological_sort(reg)
        # a must come before b, b before c
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_diamond_dependency(self) -> None:
        @service("a")
        class A:
            pass

        @service("b", deps=[A])
        class B:
            pass

        @service("c", deps=[A])
        class C:
            pass

        @service("d", deps=[B, C])
        class D:
            pass

        reg = Registry()
        for cls in (A, B, C, D):
            reg.register(cls)
        order = topological_sort(reg)
        idx_a = order.index("a")
        idx_b = order.index("b")
        idx_c = order.index("c")
        idx_d = order.index("d")
        assert idx_a < idx_b
        assert idx_a < idx_c
        assert idx_b < idx_d
        assert idx_c < idx_d

    def test_independent_nodes(self) -> None:
        """Nodes with no dependencies can start in any order."""

        @service("x")
        class X:
            pass

        @service("y")
        class Y:
            pass

        @service("z")
        class Z:
            pass

        reg = Registry()
        for cls in (X, Y, Z):
            reg.register(cls)
        order = topological_sort(reg)
        assert set(order) == {"x", "y", "z"}

    def test_circular_dependency_raises(self) -> None:
        @service("a")
        class A:
            pass

        @service("b")
        class B:
            pass

        reg = Registry()
        # Register with manual dep_names to create a cycle
        reg.register(A)
        reg.register(B)
        a_entry = reg.get_by_class(A)
        a_entry.dep_names = ["b"]
        b_entry = reg.get_by_class(B)
        b_entry.dep_names = ["a"]

        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            topological_sort(reg)

    def test_self_dependency_creates_cycle(self) -> None:
        @service("self-ref")
        class SelfRef:
            pass

        reg = Registry()
        reg.register(SelfRef)
        entry = reg.get_by_class(SelfRef)
        entry.dep_names = ["self-ref"]

        with pytest.raises(CircularDependencyError):
            topological_sort(reg)

    def test_result_length_matches_input(self) -> None:
        @service("a")
        class A:
            pass

        @service("b", deps=[A])
        class B:
            pass

        reg = Registry()
        reg.register(A)
        reg.register(B)
        order = topological_sort(reg)
        assert len(order) == 2
