"""Pure graph algorithms — building and topologically sorting the unit graph.

纯图算法：建图与拓扑排序。把“扫描”与“装载”分离（借鉴 NestJS 的 scanner/loader），
算法无副作用、可独立测试，得到的拓扑序就是框架的启动顺序。
"""

from __future__ import annotations

import inspect
from collections import defaultdict, deque

from canary_framework.common.error import CircularDependencyError, ConstructionError
from canary_framework.core.decorator.introspect import deps_of, is_cocoa


def build_graph(roots: list[type]) -> dict[type, object]:
    """Instantiate every root and its transitive dependencies, one instance each.

    递归实例化每个根及其传递依赖；每个类型只实例化一次，那个实例就是整张图共享的单例。

    图上的实例**全部由框架构造**，没有第二条来源。所以"这个单元是怎么来的"永远只有一个
    答案，也就不存在"有些单元框架能造、有些得你造好交进来"的分裂。需要外界输入的事情
    一律推迟到生命周期钩子里做（见 :class:`~canary_framework.common.error.ConstructionError`）。
    """
    graph: dict[type, object] = {}

    def visit(t: type) -> None:
        if t in graph:
            return
        if not is_cocoa(t):
            raise TypeError(f"'{t.__name__}' is not decorated with @cocoa")
        graph[t] = _construct(t)
        for dep in deps_of(t):
            visit(dep)

    for root in roots:
        visit(root)
    return graph


def _construct(t: type) -> object:
    """Instantiate *t* with no arguments, turning an arity mismatch into a real error.

    先看签名再调用：签名对不上说明它需要构造参数，那是框架的一条硬约束，报
    :class:`ConstructionError` 并说清该往哪儿改；签名对得上就照常调用，构造器自己抛的
    异常原样传播——那是使用者的代码出错，不该被框架的错误盖住。
    """
    try:
        signature = inspect.signature(t)
    except (TypeError, ValueError):  # 内建 / C 扩展类型拿不到签名，直接试
        return t()
    try:
        signature.bind()
    except TypeError as exc:
        raise ConstructionError(t.__name__, str(exc)) from exc
    return t()


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
