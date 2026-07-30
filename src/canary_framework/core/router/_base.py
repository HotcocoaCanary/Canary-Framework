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
    """Base class for declaration-driven routers."""

    __cf_route_specs__: tuple[RouteSpec, ...] = ()

    def __init__(self) -> None:
        """Initialize a router and defer standalone dependency assembly."""
        super().__init__()
        self._cf_dependency_engine: DependencyEngine | None = None

    @property
    def route_specs(self) -> tuple[RouteSpec, ...]:
        """Return immutable route specifications declared on this router class."""
        return self.__cf_route_specs__

    def _standalone_config(self) -> CanaryConfig:
        """Create and apply this router's standalone configuration once."""
        if self._cf_config is None:
            meta = get_router_meta(type(self))
            config_cls = (
                CanaryConfig if meta is None or meta.config_cls is None else meta.config_cls
            )
            self._cf_config = config_cls()
            ensure_logging(self._cf_config.log_level)
        return self._cf_config

    async def _init(self) -> None:
        """Initialize dependencies only when this router is a root node."""
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
        """Start standalone dependencies in dependency order."""
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.startup()

    async def _shutdown(self) -> None:
        """Stop standalone dependencies in reverse dependency order."""
        if self._cf_dependency_engine is not None:
            await self._cf_dependency_engine.shutdown()

    async def _rollback_phase(self, *, started: bool) -> None:
        """Roll back standalone dependencies after a lifecycle failure."""
        if self._cf_dependency_engine is None:
            return
        if started:
            await self._cf_dependency_engine.rollback_started()
        else:
            await self._cf_dependency_engine.rollback_initialized()

    def _collect_routes(self, context: RouteContext) -> tuple[ResolvedRoute, ...]:
        """Resolve this router's routes against an inherited route context."""
        meta = get_router_meta(type(self))
        if meta is None:
            raise TypeError(f"{type(self).__name__} must be decorated with @router.")
        return resolve_router_routes(self, meta, context)


__all__ = ["RouterBase"]
