"""Unit tests for the pure graph algorithms."""

import pytest

from canary_framework import cocoa
from canary_framework.common.error import CircularDependencyError
from canary_framework.runtime import build_graph, topological_sort

pytestmark = pytest.mark.unit


def test_build_graph_instantiates_transitively_once() -> None:
    @cocoa
    class Config: ...

    @cocoa(deps=[Config])
    class Database: ...

    @cocoa(deps=[Database])
    class Repo: ...

    graph = build_graph([Repo])
    assert set(graph) == {Config, Database, Repo}
    assert isinstance(graph[Config], Config)
    assert isinstance(graph[Database], Database)
    assert isinstance(graph[Repo], Repo)


def test_build_graph_instantiates_each_type_once() -> None:
    @cocoa
    class Config: ...

    @cocoa(deps=[Config])
    class A: ...

    @cocoa(deps=[Config])
    class B: ...

    graph = build_graph([A, B])
    assert set(graph) == {Config, A, B}
    assert all(isinstance(inst, t) for t, inst in graph.items())


def test_build_graph_rejects_non_cocoa_dependency() -> None:
    class Plain:
        pass

    @cocoa(deps=[Plain])
    class Bad:
        pass

    with pytest.raises(TypeError, match="not decorated with @cocoa"):
        build_graph([Bad])


def test_topological_sort_orders_dependencies_first() -> None:
    @cocoa
    class A: ...

    @cocoa(deps=[A])
    class B: ...

    @cocoa(deps=[B])
    class C: ...

    order = topological_sort(build_graph([C]))
    assert order.index(A) < order.index(B) < order.index(C)


def test_topological_sort_detects_cycle() -> None:
    @cocoa
    class A: ...

    @cocoa(deps=[A])
    class B: ...

    A.__cocoa_deps__ = [B]  # close the loop A <-> B

    with pytest.raises(CircularDependencyError):
        topological_sort(build_graph([A]))
