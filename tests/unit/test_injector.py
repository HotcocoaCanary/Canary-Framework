"""Unit tests for engine.injector module."""

import pytest

from canary_framework.common import CF_SERVICE_MARKER, ServiceMeta
from canary_framework.engine.injector import topological_sort
from canary_framework.engine.registry import Registry


@pytest.mark.unit
class TestTopologicalSort:
    """Tests for topological_sort function."""

    def test_simple_dependency_chain(self) -> None:
        """Test simple dependency chain via annotations."""
        reg = Registry()

        class C:
            pass

        class B:
            c: C

        class A:
            b: B

        for cls in (A, B, C):
            setattr(cls, CF_SERVICE_MARKER, True)

        reg.register(A, meta=ServiceMeta(name="a"))
        reg.register(B, meta=ServiceMeta(name="b"))
        reg.register(C, meta=ServiceMeta(name="c"))

        result = topological_sort(reg)
        assert result == ["c", "b", "a"]

    def test_no_dependencies(self) -> None:
        """Test services with no dependencies."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        reg.register(A, meta=ServiceMeta(name="a"))
        reg.register(B, meta=ServiceMeta(name="b"))

        result = topological_sort(reg)
        assert set(result) == {"a", "b"}
