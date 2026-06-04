"""拓扑排序工具。

提供基于类型注解的依赖拓扑排序。

Topological sorting utility.

Provides topological sorting based on type annotation dependencies.
"""

from __future__ import annotations

from collections import defaultdict, deque

from canary_framework.common import CircularDependencyError
from canary_framework.common.markers import resolve_deps
from canary_framework.engine.logging import get_logger
from canary_framework.engine.registry import Registry

_log = get_logger("di")


def topological_sort(registry: Registry) -> list[str]:
    """对注册表中的服务进行拓扑排序。

    通过 resolve_deps() 读取类注解自动构建依赖图。
    如果检测到循环依赖，抛出CircularDependencyError。

    Args:
        registry: 服务注册表。

    Returns:
        按依赖顺序排列的服务名称列表。

    Raises:
        CircularDependencyError: 如果检测到循环依赖。

    Produce a valid startup order using annotation-driven dependency graph.

    Args:
        registry: The service registry.

    Returns:
        List of service names ordered by dependencies.

    Raises:
        CircularDependencyError: If a circular dependency is detected.
    """
    names = registry.names()
    in_degree: dict[str, int] = dict.fromkeys(names, 0)
    adjacency: dict[str, list[str]] = defaultdict(list)

    for entry in registry.all_entries():
        for dep_type in resolve_deps(entry.cls).values():
            try:
                dep_entry = registry.get_by_class(dep_type)
            except Exception:
                continue
            if dep_entry.name in names:
                adjacency[dep_entry.name].append(entry.name)
                in_degree[entry.name] += 1

    queue = deque(n for n, d in in_degree.items() if d == 0)
    result: list[str] = []

    while queue:
        cur = queue.popleft()
        result.append(cur)
        for neighbour in adjacency[cur]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(result) != len(names):
        cyclic = [n for n in names if n not in result]
        _log.error("Circular dependency detected: %s", cyclic)
        raise CircularDependencyError(f"Circular dependency detected among: {sorted(cyclic)}")

    _log.debug("Topological sort result: %s", " → ".join(result))
    return result


__all__ = ["topological_sort"]
