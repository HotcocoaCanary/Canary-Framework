"""ModuleBase — 通过生命周期阶段协调子服务的模块基类。

处理实例化、依赖注入、按拓扑顺序执行init/startup/shutdown，
并暴露Starlette Router用于ASGI挂载。

ModuleBase — orchestrates child services through lifecycle phases.

Handles instantiation, DI wiring, init/startup/shutdown
in topological order, and exposes a starlette Router for ASGI mounting.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import cast, override

from starlette.routing import Mount, Route
from starlette.routing import Router as StarletteRouter
from starlette.types import ASGIApp

from canary_framework.common import (
    CanaryConfig,
    DependencyInjectionError,
    LifecycleAware,
    ServiceMeta,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)
from canary_framework.common.logging import ensure_logging, get_logger
from canary_framework.core.router import Router as _Router
from canary_framework.core.router import _collect_routes
from canary_framework.core.service import ServiceBase
from canary_framework.engine.dependencies import resolve_deps, topological_sort
from canary_framework.engine.registry import Registry

_log = get_logger("module")


def _wire_service(inst: object, registry: Registry) -> None:
    """注入 registry 中的依赖到实例。"""
    for attr_name, dep_cls in resolve_deps(type(inst)).items():
        setattr(inst, attr_name, registry.get_by_class(dep_cls).instance)


class ModuleBase(ServiceBase):
    """@module装饰类的自动注入基类。

    协调子服务生命周期——实例化、依赖注入、按拓扑顺序执行
    init/startup/shutdown。

    支持通过 config 对象配置文档端点：
    - cf_docs_path: OpenAPI JSON 端点路径（默认 /openapi.json）
    - cf_swagger_path: Swagger UI 路径（默认 /docs）
    - cf_redoc_path: ReDoc 路径（默认 /redoc）
    - cf_swagger_cdn: Swagger UI CDN 基 URL
    - cf_redoc_cdn: ReDoc CDN 基 URL
    - cf_servers: OpenAPI servers 列表
    - cf_security_schemes: OpenAPI security schemes

    Auto-injected base for @module-decorated classes.

    Orchestrates child service lifecycle — instantiation, DI wiring,
    init/startup/shutdown in topological order.
    """

    def __init__(self) -> None:
        """初始化ModuleBase实例。

        Config 在 __init__ 时立即实例化，确保日志等级在
        任何服务初始化之前生效。

        Initialize the ModuleBase instance.

        Config is instantiated immediately so log_level takes effect
        before any service initialization.
        """
        super().__init__()
        self._cf_registry: Registry | None = None
        self._cf_startup_order: list[str] = []
        self._cf_asgi_app: StarletteRouter | None = None
        self._cf_config: CanaryConfig | None = None

        meta = get_module_meta(type(self))
        if meta is not None and meta.config_cls is not None:
            self._cf_config = meta.config_cls()
            ensure_logging(self._cf_config.log_level)
        else:
            ensure_logging("INFO")

    def _iter_instances(
        self, *, skip_none: bool = False
    ) -> Generator[tuple[str, object], None, None]:
        """迭代所有子服务实例（按启动顺序）。

        Iterate all child service instances in startup order.
        """
        registry = self._cf_registry
        if registry is None:
            return
        for name in self._cf_startup_order:
            inst = registry.get_by_name(name).instance
            if inst is None:
                if skip_none:
                    continue
                raise DependencyInjectionError(f"Service '{name}' instance is None.")
            yield name, inst

    @override
    def init(self) -> None:
        """初始化模块及其所有子服务。

        实例化所有服务、注入依赖、按拓扑顺序调用每个服务的init方法。
        config 已在 __init__ 中实例化，此处将 _cf_config 传播给子服务。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Initialize the module and all its child services.

        Instantiates all services, injects dependencies, calls init on each
        child service in topological order. Propagates _cf_config to children.
        """
        _log.info("Initializing module: %s", type(self).__name__)

        meta = get_module_meta(type(self))
        if meta is None or not meta.services:
            return

        parent_registry = getattr(self, "_cf_parent_registry", None)
        registry = Registry(parent=parent_registry)
        self._cf_registry = registry
        for sub_cls in meta.services:
            self._register_entry_with_deps(sub_cls, registry)

        self._cf_startup_order = topological_sort(registry)
        if not self._cf_startup_order:
            return

        # 阶段1: 实例化 + 注入依赖（按拓扑序，一趟完成）
        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            inst = entry.cls()
            entry.instance = inst
            _wire_service(inst, registry)
            if isinstance(inst, ServiceBase):
                inst._cf_parent_registry = registry
                if not hasattr(inst, "_cf_config") or inst._cf_config is None:
                    inst._cf_config = self._cf_config  # type: ignore[attr-defined]
            cls_name = entry.cls.__name__
            if not cls_name.startswith("_cf_"):
                setattr(self, cls_name, inst)

        _wire_service(self, registry)

        # 阶段2: 调用子服务 init()
        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            child = entry.instance
            if child is None:
                raise DependencyInjectionError(f"Service '{name}' instance is None during init.")
            child.init()  # type: ignore[attr-defined]

        super().init()

    @property
    def asgi_app(self) -> StarletteRouter:
        """获取ASGI应用。

        懒加载创建Starlette路由器，挂载所有具有asgi_app属性的子服务。
        同时收集子服务提供的根路径路由。

        Returns:
            StarletteRouter实例。

        Get the ASGI application.

        Lazily creates the Starlette router with mounts for all child services
        that have an asgi_app attribute, plus root-level routes from children.
        """
        if self._cf_asgi_app is None:
            routes: list[Mount | Route] = []
            mount_paths: set[str] = set()

            own_router = getattr(self, "router", None)
            if isinstance(own_router, _Router):
                for route in _collect_routes(self, include_router_prefix=False):
                    routes.append(route)
                    mount_paths.add(route.path)
            for name, inst in self._iter_instances(skip_none=True):
                asgi = getattr(inst, "asgi_app", None)
                if asgi is not None:
                    app = cast(ASGIApp, asgi)
                    mount_path = (
                        inst.get_mount_path() if hasattr(inst, "get_mount_path") else f"/{name}"
                    )
                    if mount_path in mount_paths:
                        raise ValueError(f"Mount path collision: '{mount_path}' is already in use.")
                    routes.append(Mount(mount_path, app=app))
                    mount_paths.add(mount_path)
            for route in self._cf_get_root_routes():
                if route.path in mount_paths:
                    raise ValueError(
                        f"Root route path collision: '{route.path}' is already in use."
                    )
                routes.append(route)
                mount_paths.add(route.path)
            if self._cf_root_routes:
                for route in self._cf_root_routes:
                    if route.path not in mount_paths:
                        routes.append(route)
                        mount_paths.add(route.path)
            self._cf_asgi_app = StarletteRouter(routes)
        return self._cf_asgi_app

    def _cf_get_root_routes(self) -> list[Route]:
        """合并所有子服务（包括子模块）的根路径路由，去重后返回。

        解决嵌套 Module 场景下，带有 Router 属性的 Service 生成的文档路由
        （如 /docs, /redoc, /openapi.json）无法传播到根 ASGI 应用的问题。

        Aggregate root-level routes from all child services including
        sub-modules, deduplicated by path.
        """
        routes: list[Route] = []
        seen: set[str] = set()
        for _, inst in self._iter_instances(skip_none=True):
            if hasattr(inst, "_cf_get_root_routes"):
                for route in inst._cf_get_root_routes():
                    if route.path not in seen:
                        routes.append(route)
                        seen.add(route.path)
        return routes

    @override
    async def startup(self) -> None:
        """启动模块及其所有子服务。

        调用BEFORE_STARTUP钩子和OpenAPI设置（通过super），
        然后按拓扑顺序调用每个子服务的startup方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Start the module and all its child services.

        Invokes the BEFORE_STARTUP hook and OpenAPI setup (via super),
        then calls startup on each child service in topological order.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        _log.info("Starting module: %s", type(self).__name__)
        await super().startup()
        for _, child in self._iter_instances():
            await cast(LifecycleAware, child).startup()

    @override
    async def shutdown(self) -> None:
        """关闭模块及其所有子服务。

        调用BEFORE_SHUTDOWN钩子，然后按逆拓扑顺序调用每个子服务的shutdown方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Shutdown the module and all its child services.

        Invokes the BEFORE_SHUTDOWN hook, then calls shutdown on each child service
        in reverse topological order.

        Raises:
            DependencyInjectionError: 如果服务实例为None。
        """
        _log.info("Shutting down module: %s", type(self).__name__)
        await super().shutdown()
        children = list(self._iter_instances())
        for _, child in reversed(children):
            await cast(LifecycleAware, child).shutdown()

    def _register_entry_with_deps(self, cls: type, registry: Registry) -> None:
        """递归注册服务及其依赖。

        如果服务/模块已在当前或父注册表中注册，则跳过。
        否则注册它并递归注册其依赖。

        Args:
            cls: 要注册的类。
            registry: 目标注册表。

        Raises:
            TypeError: 如果类没有被@service或@module装饰。

        Recursively register a service and its dependencies.

        Skips if the service/module is already registered in current or parent registry.
        Otherwise registers it and recursively registers its dependencies.

        Args:
            cls: The class to register.
            registry: The target registry.

        Raises:
            TypeError: If the class is not decorated with @service or @module.
        """
        if registry.has(cls):
            return

        if is_cf_module(cls):
            mod_meta = get_module_meta(cls)
            if mod_meta is not None:
                registry.register(cls, meta=mod_meta)
            for dep_cls in resolve_deps(cls).values():
                self._register_entry_with_deps(dep_cls, registry)
            return

        if is_cf_service(cls):
            svc_meta = get_service_meta(cls)
            if svc_meta is not None:
                registry.register(cls, meta=svc_meta)
            else:
                registry.register(cls, meta=ServiceMeta(name=cls.__name__))
            for dep_cls in resolve_deps(cls).values():
                self._register_entry_with_deps(dep_cls, registry)
            return

        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")


__all__ = ["ModuleBase"]
