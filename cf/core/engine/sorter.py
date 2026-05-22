from __future__ import annotations

from collections import defaultdict, deque

from cf.core.registry.registry import Registry


def topological_sort(registry: Registry) -> list[str]:
    names = registry.names()
    in_degree: dict[str, int] = {n: 0 for n in names}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for entry in registry.all_entries():
        for dep_name in entry.dep_names:
            adjacency[dep_name].append(entry.name)
            in_degree[entry.name] += 1

    queue = deque(n for n, d in in_degree.items() if d == 0)
    result: list[str] = []

    while queue:
        cur = queue.popleft()
        result.append(cur)
        for neighbor in adjacency[cur]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(names):
        cyclic = [n for n in names if n not in result]
        raise RuntimeError(f"Circular dependency detected: {cyclic}")

    return result
