"""拓扑排序引擎 —— Kahn's BFS 算法。

根据服务的 dep_names 依赖关系构建有向图，计算出安全启动顺序。
被依赖方先于依赖方启动；检测到循环依赖时抛出 RuntimeError。
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque

from cf.core.registry.registry import Registry

_log = logging.getLogger("cf.sorter")


def topological_sort(registry: Registry) -> list[str]:
    """使用 Kahn 算法对注册表进行拓扑排序。

    Args:
        registry: 全局注册表，包含所有已注册服务/模块的 dep_names。

    Returns:
        服务名称列表，按「被依赖方在前 → 依赖方在后」排列。

    Raises:
        RuntimeError: 检测到循环依赖。

    算法步骤:
        1. 为每个节点初始化入度 0
        2. 遍历 dep_names: 添加边 dep_name → entry.name，依赖者入度 +1
        3. 入度为 0 的节点入队（无依赖，可直接启动）
        4. BFS: 依次处理队列节点，将其后继的入度减 1，入度归零时入队
        5. 结果数 != 节点总数 → 循环依赖
    """
    names = registry.names()

    # 入度表: 节点还需等待多少个依赖
    in_degree: dict[str, int] = {n: 0 for n in names}
    # 邻接表: 被依赖者 → [依赖者列表]
    adjacency: dict[str, list[str]] = defaultdict(list)

    for entry in registry.all_entries():
        for dep_name in entry.dep_names:
            adjacency[dep_name].append(entry.name)
            in_degree[entry.name] += 1

    # BFS 队列: 入度为 0 的节点（无依赖，可率先启动）
    queue = deque(n for n, d in in_degree.items() if d == 0)
    result: list[str] = []

    while queue:
        cur = queue.popleft()
        result.append(cur)
        for neighbor in adjacency[cur]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 循环依赖检测
    if len(result) != len(names):
        cyclic = [n for n in names if n not in result]
        _log.error("Circular dependency detected: %s", cyclic)
        raise RuntimeError(f"Circular dependency detected: {cyclic}")

    _log.debug("Topological sort result: %s", " → ".join(result))
    return result
