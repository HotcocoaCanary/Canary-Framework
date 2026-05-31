"""Dependency injection utilities — naming, topological sort, and dependency wiring."""

from __future__ import annotations

import re
from collections import defaultdict, deque

from canary_framework.common import (
    CircularDependencyError,
    DependencyInjectionError,
    ServiceEntry,
)
from canary_framework.engine.logging import get_logger
from canary_framework.engine.registry import Registry

_log = get_logger("di")

# ============================================================================
# PascalCase → snake_case
# ============================================================================

_CAMEL_SPLIT: re.Pattern[str] = re.compile(
    r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+)"
)


def to_snake(name: str) -> str:
    parts: list[str] = _CAMEL_SPLIT.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)


# ============================================================================
# Kahn BFS topological sort
# ============================================================================


def topological_sort(registry: Registry) -> list[str]:
    """Produce a valid startup order for all registered services.

    Dependees come before dependants.  Raises ``CircularDependencyError``
    if a cycle is detected.
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
        raise CircularDependencyError(
            f"Circular dependency detected among: {sorted(cyclic)}"
        )

    _log.debug("Topological sort result: %s", " → ".join(result))
    return result


# ============================================================================
# Dependency injection engine
# ============================================================================


def inject_deps(instance: object, entry: ServiceEntry, registry: Registry) -> None:
    """Inject declared dependencies as snake_case attributes on *instance*."""
    for dep_cls in entry.deps:
        dep_entry = registry.get_by_class(dep_cls)
        if dep_entry.instance is None:
            raise DependencyInjectionError(
                f"Cannot inject '{dep_cls.__name__}' into '{entry.name}': "
                f"the dependency instance is None."
            )
        attr_name = to_snake(dep_cls.__name__)
        setattr(instance, attr_name, dep_entry.instance)
        _log.debug("  %s  →  self.%s", dep_cls.__name__, attr_name)


__all__ = ["inject_deps", "to_snake", "topological_sort"]
