"""Strict dependency resolution and graph ordering.

依赖声明从类级别注解解析为带属性名称的不可变规格。
Dependency declarations are resolved from class annotations into immutable specs.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, get_type_hints

from canary_framework.common import (
    CircularDependencyError,
    DependencyDirectionError,
    DependencyInjectionError,
    is_cf_module,
    is_cf_router,
    is_cf_service,
    unwrap_optional,
)


@dataclass(frozen=True, slots=True)
class DependencySpec:
    """One class-level dependency declaration."""

    attribute: str
    target: type


def _declaration_order(cls: type) -> tuple[tuple[str, Any], ...]:
    """Collect class annotations base-first while preserving declaration order."""
    ordered: dict[str, Any] = {}
    for base in reversed(cls.__mro__):
        for name, annotation in vars(base).get("__annotations__", {}).items():
            ordered[name] = annotation
    return tuple(ordered.items())


def _resolution_error(cls: type, annotations: tuple[tuple[str, Any], ...], exc: Exception) -> None:
    """Raise a contextual error for a failed type-hint evaluation."""
    missing_name: str | None = None
    match = re.search(r"name ['\"]([^'\"]+)['\"] is not defined", str(exc))
    if match:
        missing_name = match.group(1)

    attribute = "<unknown>"
    annotation: Any = missing_name or str(exc)
    for name, raw in annotations:
        if missing_name is None or missing_name in repr(raw):
            attribute = name
            annotation = raw
            break
    raise DependencyInjectionError(
        f"Failed to resolve dependency annotation for {cls.__name__}.{attribute}: {annotation}"
    ) from exc


def validate_dependency_direction(owner: type, dependency: DependencySpec) -> None:
    """Reject edges that point upward in the service/router/module layers."""
    target = dependency.target
    if is_cf_module(owner):
        return
    if is_cf_router(owner):
        if is_cf_router(target) or is_cf_module(target):
            raise DependencyDirectionError(
                f"Router {owner.__name__}.{dependency.attribute} may depend only on Service; "
                f"got {target.__name__}."
            )
        return
    if is_cf_router(target):
        raise DependencyDirectionError(
            f"Service {owner.__name__}.{dependency.attribute} may not depend on Router "
            f"{target.__name__}."
        )


def resolve_deps(cls: type) -> tuple[DependencySpec, ...]:
    """Resolve marked class annotations in base-to-derived declaration order."""
    declarations = _declaration_order(cls)
    try:
        hints = get_type_hints(cls)
    except Exception as exc:
        _resolution_error(cls, declarations, exc)

    resolved: list[DependencySpec] = []
    for attribute, _ in declarations:
        if attribute not in hints:
            continue
        target, _nullable = unwrap_optional(hints[attribute])
        if isinstance(target, type) and is_cf_service(target):
            dependency = DependencySpec(attribute=attribute, target=target)
            validate_dependency_direction(cls, dependency)
            resolved.append(dependency)
    return tuple(resolved)


def _cycle_path(
    graph: Mapping[type, tuple[DependencySpec, ...]], residual: set[type], start: type
) -> str:
    """Find and format one actual residual cycle with its edge attributes."""
    visiting: dict[type, int] = {}
    nodes: list[type] = []
    edges: list[DependencySpec] = []

    def walk(owner: type) -> str | None:
        visiting[owner] = len(nodes)
        nodes.append(owner)
        for dependency in graph.get(owner, ()):
            target = dependency.target
            if target not in residual:
                continue
            if target in visiting:
                begin = visiting[target]
                cycle_edges = [*edges[begin:], dependency]
                text = " -> ".join(
                    f"{node.__name__}.{edge.attribute}"
                    for node, edge in zip(nodes[begin:], cycle_edges, strict=True)
                )
                return f"{text} -> {target.__name__}"
            edges.append(dependency)
            found = walk(target)
            if found is not None:
                return found
            edges.pop()
        nodes.pop()
        visiting.pop(owner)
        return None

    found = walk(start)
    if found is not None:
        return found
    return " -> ".join(node.__name__ for node in residual)


def topological_sort(
    graph: Mapping[type, tuple[DependencySpec, ...]],
) -> tuple[type, ...]:
    """Return stable dependency-first ordering or report an attributed cycle."""
    declaration_order = tuple(graph)
    in_degree: dict[type, int] = dict.fromkeys(declaration_order, 0)
    adjacency: dict[type, list[type]] = defaultdict(list)

    for owner in declaration_order:
        for dependency in graph[owner]:
            target = dependency.target
            if target not in in_degree:
                continue
            adjacency[target].append(owner)
            in_degree[owner] += 1

    queue = deque(node for node in declaration_order if in_degree[node] == 0)
    result: list[type] = []
    while queue:
        current = queue.popleft()
        result.append(current)
        for dependent in adjacency[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(declaration_order):
        residual = set(declaration_order) - set(result)
        start = next(node for node in declaration_order if node in residual)
        path = _cycle_path(graph, residual, start)
        raise CircularDependencyError(f"Circular dependency detected: {path}")
    return tuple(result)


__all__ = [
    "DependencySpec",
    "resolve_deps",
    "topological_sort",
    "validate_dependency_direction",
]
