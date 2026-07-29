"""Scoped dependency graph construction and lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, cast

from canary_framework.common import (
    CanaryConfig,
    DependencyInjectionError,
    ServiceMeta,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)
from canary_framework.common.types import LifecycleState
from canary_framework.engine.dependencies import DependencySpec, resolve_deps, topological_sort
from canary_framework.engine.registry import Registry


class _LifecycleNode(Protocol):
    _cf_parent_registry: object | None
    _cf_config: CanaryConfig | None
    lifecycle_state: LifecycleState

    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def _rollback(self, *, started: bool) -> None: ...


def _metadata(cls: type) -> ServiceMeta:
    """Return a registry name for any marked framework node."""
    meta = get_service_meta(cls)
    if meta is None:
        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")
    return meta


class DependencyEngine:
    """Build one registry scope and drive its nodes in dependency order."""

    def __init__(
        self,
        *,
        children: Iterable[type],
        parent_registry: Registry | None,
        config: CanaryConfig | None,
    ) -> None:
        self.registry = Registry(parent=parent_registry)
        self._child_classes = tuple(children)
        self._config = config
        self._order: tuple[type, ...] = ()
        self._direct_children: tuple[_LifecycleNode, ...] = ()
        self._initialized: list[_LifecycleNode] = []
        self._started: list[_LifecycleNode] = []

    @property
    def direct_children(self) -> tuple[_LifecycleNode, ...]:
        """Return direct children in declaration order."""
        return self._direct_children

    @property
    def config(self) -> CanaryConfig | None:
        """Return the config nearest to this scope."""
        return self._config

    async def init(self) -> None:
        """Register, instantiate, wire, and initialize this scope."""
        self._register_graph()
        self._instantiate_and_wire()
        try:
            for cls in self._order:
                node = cast(_LifecycleNode, self.registry.get(cls))
                await node.init()
                self._initialized.append(node)
        except Exception:
            await self.rollback_initialized()
            raise

    async def startup(self) -> None:
        """Start initialized nodes in dependency order."""
        try:
            for cls in self._order:
                node = cast(_LifecycleNode, self.registry.get(cls))
                await node.startup()
                self._started.append(node)
        except Exception:
            await self.rollback_started()
            raise

    async def shutdown(self) -> None:
        """Stop started nodes in reverse dependency order."""
        for node in reversed(self._started):
            if node.lifecycle_state is LifecycleState.STARTED:
                await node.shutdown()
        self._started.clear()
        self._initialized.clear()

    async def rollback_initialized(self) -> None:
        """Roll back successful initialization in reverse order."""
        await self._rollback(self._initialized, started=False)
        self._initialized.clear()

    async def rollback_started(self) -> None:
        """Roll back successful startup in reverse order."""
        await self._rollback(self._started, started=True)
        self._started.clear()
        self._initialized.clear()

    async def _rollback(self, nodes: list[_LifecycleNode], *, started: bool) -> None:
        for node in reversed(nodes):
            await node._rollback(started=started)

    def _register_graph(self) -> None:
        """Construct the local graph while leaving nested module descendants scoped."""
        for cls in self._child_classes:
            self._register_local(cls)

        graph: dict[type, tuple[DependencySpec, ...]] = {}
        for entry in self.registry.local_entries():
            deps = list(resolve_deps(entry.cls))
            if is_cf_module(entry.cls):
                for dependency in self._descendant_dependencies(entry.cls):
                    if self.registry.has_local(dependency.target):
                        deps.append(dependency)
            graph[entry.cls] = tuple(_unique_specs(deps))
        self._order = topological_sort(graph)

    def _register_local(self, cls: type) -> None:
        """Register an owned node and its ordinary transitive dependencies."""
        if self.registry.has_local(cls):
            return
        if not is_cf_service(cls):
            raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")
        self.registry.register(cls, meta=_metadata(cls))
        for dependency in resolve_deps(cls):
            if self.registry.has(dependency.target):
                continue
            self._register_local(dependency.target)

    def _descendant_dependencies(
        self, cls: type, seen: set[type] | None = None
    ) -> tuple[DependencySpec, ...]:
        """Find dependencies consumed below a module for promoted-edge ordering."""
        visited = set() if seen is None else seen
        if cls in visited:
            return ()
        visited.add(cls)
        dependencies: list[DependencySpec] = []
        for dependency in resolve_deps(cls):
            dependencies.append(dependency)
            dependencies.extend(self._descendant_dependencies(dependency.target, visited))
        meta = get_module_meta(cls)
        if meta is not None:
            for child in meta.children:
                dependencies.extend(self._descendant_dependencies(child, visited))
        return tuple(dependencies)

    def _instantiate_and_wire(self) -> None:
        """Instantiate each local node once and wire local or inherited targets."""
        for cls in self._order:
            entry = self.registry.get_by_class(cls)
            instance = cls()
            entry.instance = instance
            node = cast(_LifecycleNode, instance)
            node._cf_parent_registry = self.registry
            if node._cf_config is None:
                node._cf_config = self._config

        for entry in self.registry.local_entries():
            instance = entry.instance
            if instance is None:
                raise DependencyInjectionError(
                    f"Service '{entry.name}' instance is None during wiring."
                )
            for dependency in resolve_deps(entry.cls):
                try:
                    target = self.registry.get(dependency.target)
                except Exception as exc:
                    raise DependencyInjectionError(
                        f"Failed to inject {entry.cls.__name__}.{dependency.attribute} "
                        f"from {dependency.target.__name__}."
                    ) from exc
                setattr(instance, dependency.attribute, target)

        self._direct_children = tuple(
            cast(_LifecycleNode, self.registry.get(cls)) for cls in self._child_classes
        )


def _unique_specs(specs: Iterable[DependencySpec]) -> tuple[DependencySpec, ...]:
    result: list[DependencySpec] = []
    seen: set[tuple[str, type]] = set()
    for spec in specs:
        key = (spec.attribute, spec.target)
        if key not in seen:
            seen.add(key)
            result.append(spec)
    return tuple(result)


__all__ = ["DependencyEngine"]
