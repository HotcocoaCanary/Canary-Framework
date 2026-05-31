"""依赖注入和拓扑排序工具。

提供to_snake命名转换、依赖注入和拓扑排序功能。

Dependency injection and topological sorting utilities.

Provides to_snake name conversion, dependency injection, and topological sorting.
"""

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

_CAMEL_SPLIT: re.Pattern[str] = re.compile(
    r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+)"
)


def to_snake(name: str) -> str:
    """将驼峰命名转换为蛇形命名。

    将PascalCase或camelCase转换为snake_case。

    Args:
        name: 要转换的名称。

    Returns:
        转换后的蛇形命名。

    Convert camelCase or PascalCase to snake_case.

    Args:
        name: The name to convert.

    Returns:
        The converted snake_case name.
    """
    parts: list[str] = _CAMEL_SPLIT.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)


def topological_sort(registry: Registry) -> list[str]:
    """对注册表中的服务进行拓扑排序。

    生成所有已注册服务的有效启动顺序。依赖项在依赖者之前。
    如果检测到循环依赖，抛出CircularDependencyError。

    Args:
        registry: 服务注册表。

    Returns:
        按依赖顺序排列的服务名称列表。

    Raises:
        CircularDependencyError: 如果检测到循环依赖。

    Produce a valid startup order for all registered services.

    Dependees come before dependants. Raises ``CircularDependencyError``
    if a cycle is detected.

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


def inject_deps(instance: object, entry: ServiceEntry, registry: Registry) -> None:
    """将依赖注入到服务实例中。

    将声明的依赖作为snake_case属性注入到实例上。

    Args:
        instance: 要注入依赖的服务实例。
        entry: 服务条目，包含依赖信息。
        registry: 服务注册表。

    Raises:
        DependencyInjectionError: 如果依赖实例为None。

    Inject declared dependencies as snake_case attributes on *instance*.

    Args:
        instance: The service instance to inject dependencies into.
        entry: The service entry containing dependency information.
        registry: The service registry.

    Raises:
        DependencyInjectionError: If a dependency instance is None.
    """
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