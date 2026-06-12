"""Dependency resolution and topological sorting.

Provides resolve_deps for extracting type-annotation-based dependencies,
and topological_sort for producing a valid startup order via Kahn's algorithm.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from types import UnionType
from typing import get_args, get_origin

from canary_framework.common import (
    CF_SERVICE_MARKER,
    CircularDependencyError,
    ServiceNotFoundError,
)
from canary_framework.common.logging import get_logger
from canary_framework.engine.registry import Registry

_log = get_logger("di")


def resolve_deps(cls: type) -> dict[str, type]:
    """Extract service dependencies from type annotations.

    Scans type hints of __init__ for attributes whose annotation
    is a class carrying CF_SERVICE_MARKER. Unwraps Optional[T] and
    T | None to discover the underlying service type.

    Args:
        cls: The service class to inspect.

    Returns:
        Dict mapping attribute names to dependency classes.
    """
    from typing import get_type_hints

    try:
        hints = get_type_hints(cls)
    except Exception as e:
        import warnings

        warnings.warn(f"Failed to resolve type hints for '{cls.__name__}': {e}", stacklevel=2)
        return {}

    resolved: dict[str, type] = {}
    import typing as _typing

    for name, tp in hints.items():
        origin = get_origin(tp)
        if origin is not None:
            args = get_args(tp)
            if origin in (Callable,) or origin is UnionType or origin is _typing.Union:
                inner = [a for a in args if a is not type(None)]
                if len(inner) == 1:
                    tp = inner[0]
        if isinstance(tp, type) and hasattr(tp, CF_SERVICE_MARKER):
            resolved[name] = tp
    return resolved


def topological_sort(registry: Registry) -> list[str]:
    """Topologically sort services in the registry by dependencies.

    Builds a dependency graph from type annotations via resolve_deps(),
    then produces a valid startup order using Kahn's algorithm.

    Args:
        registry: The service registry.

    Returns:
        List of service names in dependency order.

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
            except ServiceNotFoundError:
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


__all__ = ["resolve_deps", "topological_sort"]
