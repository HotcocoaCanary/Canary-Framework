"""Composable module runtime with nested dependency and route scopes."""

from __future__ import annotations

from typing import cast, override

from canary_framework.common import CanaryConfig, ModuleMeta, get_module_meta
from canary_framework.common.routing import ResolvedRoute, RouteContext
from canary_framework.core.router import RouterBase
from canary_framework.core.service import ServiceBase
from canary_framework.engine.container import DependencyEngine
from canary_framework.engine.dependencies import resolve_deps
from canary_framework.engine.registry import Registry
from canary_framework.engine.routing import extend_context


class ModuleBase(ServiceBase):
    """Compose declared child nodes inside one dependency scope."""

    def __init__(self) -> None:
        """Initialize the module before its child dependency scope exists."""
        super().__init__()
        self._cf_dependency_engine: DependencyEngine | None = None

    @property
    def direct_children(self) -> tuple[ServiceBase, ...]:
        """Return direct children in immutable declaration order."""
        if self._cf_dependency_engine is None:
            return ()
        return cast("tuple[ServiceBase, ...]", self._cf_dependency_engine.direct_children)

    def _module_meta(self) -> ModuleMeta:
        """Return this decorated module's immutable declaration metadata."""
        meta = get_module_meta(type(self))
        if meta is None:
            raise TypeError(f"{type(self).__name__} must be decorated with @module.")
        return meta

    def _select_config(self) -> CanaryConfig:
        """Select the nearest module config, inheriting from the parent scope."""
        meta = self._module_meta()
        if meta.config_cls is not None:
            return meta.config_cls()
        if self._cf_config is not None:
            return self._cf_config
        return CanaryConfig()

    @override
    async def _init(self) -> None:
        """Build and initialize this module's nested dependency scope."""
        config = self._select_config()
        self._cf_config = config
        engine = DependencyEngine(
            children=self._module_meta().children,
            parent_registry=cast("Registry | None", self._cf_parent_registry),
            config=config,
        )
        await engine.init()
        for dependency in resolve_deps(type(self)):
            setattr(self, dependency.attribute, engine.registry.get(dependency.target))
        self._cf_dependency_engine = engine

    @override
    async def _startup(self) -> None:
        """Start child nodes in dependency order."""
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.startup()

    @override
    async def _shutdown(self) -> None:
        """Stop child nodes in reverse dependency order."""
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.shutdown()

    @override
    async def _rollback_phase(self, *, started: bool) -> None:
        """Roll back child nodes completed before a module phase failed."""
        if self._cf_dependency_engine is None:
            return
        if started:
            await self._cf_dependency_engine.rollback_started()
        else:
            await self._cf_dependency_engine.rollback_initialized()

    def _collect_routes(self, context: RouteContext) -> tuple[ResolvedRoute, ...]:
        """Fold descendant router routes through this module's context."""
        meta = self._module_meta()
        current = extend_context(
            context,
            prefix=meta.prefix,
            tags=meta.tags,
            security=meta.security,
        )
        routes: list[ResolvedRoute] = []
        for child in self.direct_children:
            if isinstance(child, RouterBase | ModuleBase):
                routes.extend(child._collect_routes(current))
        return tuple(routes)


__all__ = ["ModuleBase"]
