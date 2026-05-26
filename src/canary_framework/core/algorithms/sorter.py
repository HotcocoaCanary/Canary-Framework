"""Topological sort via Kahn's algorithm.

设计思路 (Design rationale):
    为什么选择 Kahn (BFS) 而不是 DFS？
    （Why Kahn's BFS instead of DFS-based topological sort?）

    1. **确定性**：BFS 结果在相同输入下完全确定（队列 FIFO），
       DFS 结果依赖递归顺序，调试时不稳定
       Deterministic: BFS produces the same result for identical input.
    2. **循环检测**：Kahn 算法天然支持——遍历结束后仍有入度非零的节点
       即属于环。DFS 需要额外的染色标记来检测 back edge
       Cycle detection: nodes with remaining in-degree after the BFS
       loop are cyclic — no extra bookkeeping needed.
    3. **错误信息清晰**：可以精确列出哪些节点处于循环中
       Clear error messages: can list exactly which nodes form the cycle.

时间复杂度 (Complexity): O(V + E)，其中 V = 服务数，E = 依赖声明数。
"""

from __future__ import annotations

from collections import defaultdict, deque

from canary_framework.common._logging import get_logger
from canary_framework.common.exceptions import CircularDependencyError
from canary_framework.core.container.registry import Registry

_log = get_logger("sorter")


def topological_sort(registry: Registry) -> list[str]:
    """Produce a valid startup order for all registered services.

    使用 Kahn BFS 算法计算所有服务的安全启动顺序。
    被依赖方一定排在依赖方前面。

    Args:
        registry: 已填充的 :class:`Registry`，包含所有已注册服务。
                  The populated :class:`Registry`.

    Returns:
        拓扑序的服务名称列表。A list of service names in topological order.

    Raises:
        CircularDependencyError: 依赖图中存在环。
            The error message lists the cyclic node names.

    Algorithm (Kahn BFS):
        1. 初始化所有节点入度 = 0
        2. 遍历每条边 ``dep_name → entry.name``，将依赖者入度 +1
        3. 所有入度为 0 的节点入队（无依赖，可率先启动）
        4. BFS: 依次弹出队首，将其后继入度减 1，归零时入队
        5. ``|result| != |nodes|`` → 剩余节点形成环
    """
    names = registry.names()

    # 入度表：每个节点还需等待多少个前驱
    # In-degree: how many predecessors each node still waits for
    in_degree: dict[str, int] = dict.fromkeys(names, 0)
    # 邻接表：被依赖者 → [依赖者列表]
    # Adjacency: dep → [dependants that need dep]
    adjacency: dict[str, list[str]] = defaultdict(list)

    for entry in registry.all_entries():
        for dep_name in entry.dep_names:
            adjacency[dep_name].append(entry.name)
            in_degree[entry.name] += 1

    # BFS 队列：入度为 0 = 无依赖，可率先启动
    queue = deque(n for n, d in in_degree.items() if d == 0)
    result: list[str] = []

    while queue:
        cur = queue.popleft()
        result.append(cur)
        # 当前节点的所有后继入度减 1
        for neighbour in adjacency[cur]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    # 循环检测：仍有入度非零的节点
    if len(result) != len(names):
        cyclic = [n for n in names if n not in result]
        _log.error("Circular dependency detected: %s", cyclic)
        raise CircularDependencyError(f"Circular dependency detected among: {sorted(cyclic)}")

    _log.debug("Topological sort result: %s", " → ".join(result))
    return result
