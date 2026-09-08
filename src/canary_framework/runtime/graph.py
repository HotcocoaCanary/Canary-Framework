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

    遍历用显式栈而不是递归：依赖链的深度是**使用者的数据**，不该受 Python 递归上限的约束。
    从前一条近千节的依赖链会撞出 ``RecursionError``——那既不是框架的错误体系里的东西，也
    没告诉任何人发生了什么。访问顺序与递归版完全一致（先序深度优先），因为拓扑排序会以
    这个顺序为起点，无关节点之间的先后要保持稳定。
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

    先构造，出了 ``TypeError`` 再回头看签名——顺序很重要。反过来（每次先取签名再调用）会
    把一次 ``inspect.signature`` 摊到**每一个**单元上，而它占了建图九成的时间，却只为了
    在失败时说清楚话。成功路径上不该为失败路径付钱。

    回头看签名是为了分辨两件事：签名压根对不上（那是框架的硬约束，报
    :class:`ConstructionError` 并说清该往哪儿改），还是构造器自己的代码抛了 ``TypeError``
    （那是使用者的错误，原样传播，不该被框架的错误盖住）。
    """
    try:
        return t()
    except TypeError as exc:
        detail = _arity_problem(t)
        if detail is None:
            raise  # 签名对得上，是构造器自己抛的——不是我们的事
        raise ConstructionError(t.__name__, detail) from exc


def _arity_problem(t: type) -> str | None:
    """Explain why *t* cannot be called with no arguments, or ``None`` if it can.

    返回"为什么无参调不通"的说明；调得通（说明 ``TypeError`` 来自构造器内部）或者拿不到
    签名（内建 / C 扩展类型）时返回 ``None``。
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
