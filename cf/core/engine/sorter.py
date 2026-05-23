# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

# defaultdict：在访问不存在的键时自动创建默认值（此处为 list）
# deque：双端队列，用于 BFS 的 FIFO 队列
from collections import defaultdict, deque

# Registry：注册中心，包含所有已注册服务/模块的名称和依赖关系
from cf.core.registry.registry import Registry


def topological_sort(registry: Registry) -> list[str]:
    # 1. 获取所有已注册的服务/模块名称列表
    names = registry.names()

    # 2. 初始化入度表：每个节点的入度表示它依赖多少个其他节点未启动
    #    初始化为 0，后续遍历依赖关系时递增
    in_degree: dict[str, int] = {n: 0 for n in names}

    # 3. 初始化邻接表：key 为被依赖者，value 为依赖者的列表
    #    例如：A 被 B 依赖（B deps=[A]），则 adjacency["A"] = ["B"]
    #    含义：A 启动后，B 的入度减 1，当入度归零时 B 可以启动
    adjacency: dict[str, list[str]] = defaultdict(list)

    # 4. 遍历所有注册项，构建图结构
    for entry in registry.all_entries():
        # 遍历当前服务的每个依赖
        for dep_name in entry.dep_names:
            # 添加有向边：被依赖者 dep_name → 依赖者 entry.name
            # 这意味着 dep_name 必须先于 entry.name 启动
            adjacency[dep_name].append(entry.name)
            # 依赖者 entry.name 的入度 +1（因为它多了一个需等待启动的依赖）
            in_degree[entry.name] += 1

    # 5. 初始化 BFS 队列：收集所有入度为 0 的节点（没有依赖，可以直接启动）
    queue = deque(n for n, d in in_degree.items() if d == 0)

    # 6. 用于存储拓扑排序的结果
    result: list[str] = []

    # 7. Kahn's 算法 BFS 主循环
    while queue:
        # 从队首取出一个节点（FIFO）
        cur = queue.popleft()
        # 加入结果列表（此时该节点的所有依赖已满足）
        result.append(cur)

        # 遍历所有依赖当前节点的其他节点（即 adjacency[cur] 中的节点）
        for neighbor in adjacency[cur]:
            # 因为 cur 已经启动，neighbor 的一个依赖被满足，入度减 1
            in_degree[neighbor] -= 1
            # 如果 neighbor 的所有依赖都已满足（入度为 0），则可以启动
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 8. 循环依赖检测
    #    如果结果长度不等于总节点数，说明有入度始终不为 0 的节点（处于循环中）
    if len(result) != len(names):
        # 找出没有出现在结果中的节点（即处于循环依赖中的节点）
        cyclic = [n for n in names if n not in result]
        raise RuntimeError(f"Circular dependency detected: {cyclic}")

    return result
