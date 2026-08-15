"""Pure graph algorithms — building and topologically sorting the unit graph.

纯图算法：建图与拓扑排序。把“扫描”与“装载”分离（借鉴 NestJS 的 scanner/loader），
算法无副作用、可独立测试，得到的拓扑序就是框架的启动顺序。
"""

from __future__ import annotations

from collections import defaultdict, deque

from canary_framework.common.error import CircularDependencyError
from canary_framework.core.decorator.introspect import deps_of, is_cocoa


def build_graph(roots: list[type]) -> dict[type, object]:
    """Instantiate every root and its transitive dependencies, one instance each.

    递归实例化每个根及其传递依赖；每个类型只实例化一次，即整张图共享的单例。
    """
    graph: dict[type, object] = {}

    def visit(t: type) -> None:
        if t in graph:
            return
        if not is_cocoa(t):
            raise TypeError(f"'{t.__name__}' is not decorated with @cocoa")
        graph[t] = t()
        for dep in deps_of(t):
            visit(dep)

    for root in roots:
        visit(root)
    return graph


def topological_sort(graph: dict[type, object]) -> list[type]:
    """Kahn's algorithm — dependencies come before their dependents.

    卡恩算法求拓扑序（依赖在前）；成环则抛 :class:`CircularDependencyError`。
    """
    indegree = dict.fromkeys(graph, 0)
    dependents: dict[type, list[type]] = defaultdict(list)
    for t in graph:
        for dep in deps_of(t):
            if dep in graph:
                indegree[t] += 1
                dependents[dep].append(t)

    queue = deque(t for t in graph if indegree[t] == 0)
    order: list[type] = []
    while queue:
        t = queue.popleft()
        order.append(t)
        for other in dependents[t]:
            indegree[other] -= 1
            if indegree[other] == 0:
                queue.append(other)

    if len(order) != len(graph):
        raise CircularDependencyError([t.__name__ for t in graph if indegree[t] > 0])
    return order
