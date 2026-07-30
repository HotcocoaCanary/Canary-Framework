"""Composable module runtime with nested dependency and route scopes."""

from __future__ import annotations

from typing import cast, override

from canary_framework.common import CanaryConfig, ModuleMeta, get_module_meta
from canary_framework.common.routing import ResolvedRoute, RouteContext
from canary_framework.core._application import _ApplicationMixin
from canary_framework.core.router import RouterBase
from canary_framework.core.service import ServiceBase
from canary_framework.engine.container import DependencyEngine
from canary_framework.engine.dependencies import resolve_deps
from canary_framework.engine.registry import Registry
from canary_framework.engine.routing import extend_context


class ModuleBase(_ApplicationMixin):
    """Compose scoped children into a runnable application root."""

    def __init__(self) -> None:
        super().__init__()
        self._cf_dependency_engine: DependencyEngine | None = None

    @property
    def direct_children(self) -> tuple[ServiceBase, ...]:
        """Return instantiated children in declaration order."""
        if self._cf_dependency_engine is None:
            return ()
        return cast("tuple[ServiceBase, ...]", self._cf_dependency_engine.direct_children)

    def _module_meta(self) -> ModuleMeta:
        meta = get_module_meta(type(self))
        if meta is None:
            raise TypeError(f"{type(self).__name__} must be decorated with @module.")
        return meta

    def _select_config(self) -> CanaryConfig:
        meta = self._module_meta()
        if config_cls := meta.config_cls:
            return config_cls()
        if self._cf_config is not None:
            return self._cf_config
        return CanaryConfig()

    @override
    async def _init(self) -> None:
        if self._cf_parent_registry is None:
            self._assembly = None
        config = self._select_config()
        self._cf_config = config
        engine = DependencyEngine(
            children=self._module_meta().children,
            parent_registry=cast("Registry | None", self._cf_parent_registry),
            config=config,
        )
        await engine.init()
        self._cf_dependency_engine = engine
        for dependency in resolve_deps(type(self)):
            setattr(self, dependency.attribute, engine.registry.get(dependency.target))

    @override
    async def _startup(self) -> None:
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.startup()

    @override
    async def _shutdown(self) -> None:
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.shutdown()

    @override
    async def _rollback_phase(self, *, started: bool) -> None:
        if self._cf_dependency_engine is None:
            return
        engine = self._cf_dependency_engine
        rollback = engine.rollback_started if started else engine.rollback_initialized
        await rollback()

    def _collect_routes(self, context: RouteContext) -> tuple[ResolvedRoute, ...]:
        meta = self._module_meta()
        current = extend_context(
            context, prefix=meta.prefix, tags=meta.tags, security=meta.security
        )
        routes: list[ResolvedRoute] = []
        for child in self.direct_children:
            if isinstance(child, RouterBase | ModuleBase):
                routes.extend(child._collect_routes(current))
        return tuple(routes)


__all__ = ["ModuleBase"]
