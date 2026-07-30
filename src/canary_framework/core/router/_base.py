"""Standalone router lifecycle and immutable route resolution."""

from __future__ import annotations

from canary_framework.common import CanaryConfig, RouteContext, RouteSpec, get_router_meta
from canary_framework.common.logging import ensure_logging
from canary_framework.common.routing import ResolvedRoute
from canary_framework.core._application import _ApplicationMixin
from canary_framework.engine.container import DependencyEngine
from canary_framework.engine.dependencies import resolve_deps
from canary_framework.engine.routing import resolve_router_routes


class RouterBase(_ApplicationMixin):
    """Provide a runnable HTTP root with dependency injection and routes."""

    __cf_route_specs__: tuple[RouteSpec, ...] = ()

    def __init__(self) -> None:
        super().__init__()
        self._cf_dependency_engine: DependencyEngine | None = None

    @property
    def route_specs(self) -> tuple[RouteSpec, ...]:
        """Return endpoint declarations collected by the Router decorator."""
        return self.__cf_route_specs__

    def _standalone_config(self) -> CanaryConfig:
        if self._cf_config is None:
            meta = get_router_meta(type(self))
            config_cls = meta.config_cls if meta and meta.config_cls else CanaryConfig
            self._cf_config = config_cls()
            ensure_logging(self._cf_config.log_level)
        return self._cf_config

    async def _init(self) -> None:
        if self._cf_parent_registry is not None:
            return
        self._assembly = None
        deps = resolve_deps(type(self))
        engine = DependencyEngine(
            children=tuple(dependency.target for dependency in deps),
            parent_registry=None,
            config=self._standalone_config(),
        )
        self._cf_dependency_engine = engine
        await engine.init()
        for dependency in deps:
            setattr(self, dependency.attribute, engine.registry.get(dependency.target))
        self._cf_config = engine.config

    async def _startup(self) -> None:
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.startup()

    async def _shutdown(self) -> None:
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.shutdown()

    async def _rollback_phase(self, *, started: bool) -> None:
        if self._cf_dependency_engine is None:
            return
        engine = self._cf_dependency_engine
        rollback = engine.rollback_started if started else engine.rollback_initialized
        await rollback()

    def _collect_routes(self, context: RouteContext) -> tuple[ResolvedRoute, ...]:
        meta = get_router_meta(type(self))
        if meta is None:
            raise TypeError(f"{type(self).__name__} must be decorated with @router.")
        return resolve_router_routes(self, meta, context)


__all__ = ["RouterBase"]
