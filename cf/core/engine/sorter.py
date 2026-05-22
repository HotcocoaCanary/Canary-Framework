"""
拓扑排序引擎 —— 根据服务的依赖关系计算启动顺序。

使用 Kahn 算法（BFS 拓扑排序）：
    1. 构建入度表和邻接表（依赖关系为边，从被依赖者指向依赖者）
    2. 将所有入度为 0 的节点（无依赖的服务）入队
    3. 逐层处理队列：取出节点，加入结果列表，将其所有后继的入度减 1
    4. 如果结果列表长度不等于节点总数，则存在循环依赖

排序含义：
    依赖方必须在其所有依赖都启动后才能启动。
    拓扑排序的结果从"被依赖方"到"依赖方"排列。
    例如：A 被 B 依赖 → 排序: [A, B]，A 先启动，B 后启动
"""
from __future__ import annotations

from collections import defaultdict, deque

from cf.core.registry.registry import Registry


def topological_sort(registry: Registry) -> list[str]:
    """
    使用 Kahn 算法对注册表中的服务进行拓扑排序。

    参数：
        registry: 全局注册表，包含所有已注册的服务/模块和它们的依赖关系

    返回值：
        服务名称列表，按从"被依赖方"到"依赖方"的顺序排列

    异常：
        RuntimeError: 如果检测到循环依赖

    算法步骤：
        1. 初始化每个节点的入度为 0
        2. 遍历所有注册项，构建边：
           - 对于 entry 的每个依赖 dep_name，添加边 dep_name → entry.name
           - 含义：dep_name 必须在 entry.name 之前启动
        3. 将入度为 0 的节点入队（这些节点没有依赖，可以直接启动）
        4. BFS 处理队列，每处理一个节点，将其后继的入度减 1
        5. 如果最终结果数 != 节点总数，说明存在无法处理的节点 ── 循环依赖
    """
    names = registry.names()
    # 入度表：记录每个节点还有多少个依赖未启动
    in_degree: dict[str, int] = {n: 0 for n in names}
    # 邻接表：被依赖方 → [依赖方列表]
    # 例如：dep_name=A, entry.name=B，则 adjacency["A"] 包含 "B"
    adjacency: dict[str, list[str]] = defaultdict(list)

    for entry in registry.all_entries():
        for dep_name in entry.dep_names:
            # 添加边：被依赖者 dep_name → 依赖者 entry.name
            adjacency[dep_name].append(entry.name)
            # 依赖者的入度 +1（因为它依赖 dep_name，必须等 dep_name 先启动）
            in_degree[entry.name] += 1

    # 初始化队列：将所有入度为 0 的节点（无依赖的节点）入队
    queue = deque(n for n, d in in_degree.items() if d == 0)
    result: list[str] = []

    # BFS 拓扑排序
    while queue:
        cur = queue.popleft()  # 取出当前节点
        result.append(cur)     # 加入结果列表

        # 将该节点的所有后继（依赖当前节点的节点）的入度减 1
        for neighbor in adjacency[cur]:
            in_degree[neighbor] -= 1
            # 如果后继的入度变为 0，说明它的所有依赖都已处理，可以入队
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 检测循环依赖：如果结果数不等于节点总数，存在无法处理的节点
    if len(result) != len(names):
        # 找出形成环路的节点
        cyclic = [n for n in names if n not in result]
        raise RuntimeError(f"Circular dependency detected: {cyclic}")

    return result
