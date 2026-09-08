"""Unit tests for the pure graph algorithms."""

import sys
from typing import cast

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


def test_a_deep_dependency_chain_does_not_hit_the_recursion_limit() -> None:
    """依赖链的深度是使用者的数据，不该受 Python 递归上限的约束。

    从前建图是递归的，接近 1000 节的链会撞出 RecursionError —— 那既不在框架的错误体系里，
    也没说明发生了什么。
    """
    depth = sys.getrecursionlimit() * 3
    previous: type | None = None
    for i in range(depth):
        previous = cocoa(deps=[previous] if previous else None)(type(f"Deep{i}", (), {}))

    graph = build_graph([cast("type", previous)])
    assert len(graph) == depth
    assert len(topological_sort(graph)) == depth


def test_visit_order_is_depth_first_and_stable() -> None:
    """拓扑排序以建图顺序为起点，所以无关节点之间的先后必须稳定。"""

    @cocoa
    class Leaf1: ...

    @cocoa
    class Leaf2: ...

    @cocoa(deps=[Leaf1])
    class Left: ...

    @cocoa(deps=[Leaf2])
    class Right: ...

    @cocoa(deps=[Left, Right])
    class Root: ...

    # 先序深度优先：根 → 左子树整棵 → 右子树整棵
    assert list(build_graph([Root])) == [Root, Left, Leaf1, Right, Leaf2]
