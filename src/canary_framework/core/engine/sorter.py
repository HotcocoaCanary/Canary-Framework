"""Topological sort via Kahn's algorithm.

Computes a safe startup order for services based on their ``dep_names``
dependency declarations.  Dependencies are started before the services
that depend on them.  Cyclic graphs produce a
:class:`~canary_framework.exceptions.CircularDependencyError`.

Algorithm (Kahn, BFS):
    1. Initialise in-degree = 0 for every node.
    2. For each edge ``dep_name → entry.name``, increment the
       dependant's in-degree.
    3. Enqueue all nodes with in-degree 0 (no dependencies).
    4. While queue is non-empty: dequeue, append to result, decrement
       successors' in-degrees, enqueue any that reach 0.
    5. If ``|result| ≠ |nodes|`` → cycle detected.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque

from canary_framework.core.registry.registry import Registry
from canary_framework.exceptions import CircularDependencyError

_log = logging.getLogger("cf.sorter")


def topological_sort(registry: Registry) -> list[str]:
    """Produce a valid startup order for all registered services.

    The returned list orders services so that every dependency appears
    **before** the service that depends on it.

    Args:
        registry: The populated :class:`~canary_framework.core.registry.registry.Registry`.

    Returns:
        A list of service names in topological (startup) order.

    Raises:
        CircularDependencyError: If the dependency graph contains one or
            more cycles.  The error message lists the cyclic nodes.

    Complexity:
        O(V + E) where V = number of services, E = number of dependency
        declarations.
    """
    names = registry.names()

    in_degree: dict[str, int] = dict.fromkeys(names, 0)
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
