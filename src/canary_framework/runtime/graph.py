"""Pure graph algorithms — building and topologically sorting the unit graph.

纯图算法：建图与拓扑排序。无副作用、可独立测试，得到的拓扑序就是框架的启动顺序。
"""

from __future__ import annotations

import inspect
from collections import defaultdict, deque

from canary_framework.common.error import CircularDependencyError, ConstructionError
from canary_framework.core.decorator.introspect import deps_of, is_cocoa


def build_graph(roots: list[type]) -> dict[type, object]:
    """Instantiate every root and its transitive dependencies, one instance each.

    递归实例化每个根及其传递依赖；每个类型只实例化一次，那个实例就是整张图共享的单例。

    图上的实例全部由框架无参构造；需要外界输入的事情推迟到生命周期钩子里做
    （见 :class:`~canary_framework.common.error.ConstructionError`）。

    遍历用显式栈而非递归，依赖链的深度因此不受 Python 递归上限约束。访问顺序是先序深度
    优先，与拓扑排序的输入顺序一致，保证无关节点之间的先后稳定。
    """
    graph: dict[type, object] = {}
    stack: list[type] = list(reversed(roots))
    while stack:
        t = stack.pop()
        if t in graph:
            continue
        if not is_cocoa(t):
            raise TypeError(f"'{t.__name__}' is not decorated with @cocoa")
        graph[t] = _construct(t)
        stack.extend(reversed(deps_of(t)))
    return graph


def _construct(t: type) -> object:
    """Instantiate *t* with no arguments, turning an arity mismatch into a real error.

    先调用，出了 ``TypeError`` 再回头看签名——``inspect.signature`` 只在失败路径上跑。

    看签名是为了分辨两种 ``TypeError``：签名无法无参调用（框架约束，报
    :class:`ConstructionError`），还是构造器自身的代码抛出（使用者的错误，原样传播）。
    """
    try:
        return t()
    except TypeError as exc:
        detail = _arity_problem(t)
        if detail is None:
            raise  # 签名可以无参调用，异常来自构造器自身
        raise ConstructionError(t.__name__, detail) from exc


def _arity_problem(t: type) -> str | None:
    """Explain why *t* cannot be called with no arguments, or ``None`` if it can.

    返回"为什么无参调不通"的说明。调得通（``TypeError`` 来自构造器内部）或取不到签名
    （内建 / C 扩展类型）时返回 ``None``。
    """
    try:
        signature = inspect.signature(t)
    except (TypeError, ValueError):  # 内建 / C 扩展类型拿不到签名
        return None
    try:
        signature.bind()
    except TypeError as exc:
        return str(exc)
    return None


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
