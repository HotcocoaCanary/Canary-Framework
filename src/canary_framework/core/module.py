"""ModuleBase — 通过生命周期阶段协调子服务的模块基类。

处理实例化、依赖注入、按拓扑顺序执行configure/init/startup/shutdown，
并暴露Starlette Router用于ASGI挂载。

ModuleBase — orchestrates child services through lifecycle phases.

Handles instantiation, DI wiring, configure/init/startup/shutdown
in topological order, and exposes a starlette Router for ASGI mounting.
"""

from __future__ import annotations

from typing import cast, override

from starlette.routing import Mount
from starlette.routing import Router as StarletteRouter
from starlette.types import ASGIApp, Receive, Scope, Send

from canary_framework.common import (
    DependencyInjectionError,
    LifecycleHook,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)
from canary_framework.core.service import ServiceBase
from canary_framework.engine.hooks import LifecycleAware
from canary_framework.engine.injector import inject_deps, to_snake, topological_sort
from canary_framework.engine.registry import Registry


class ModuleBase(ServiceBase):
    """@module装饰类的自动注入基类。

    协调子服务生命周期——实例化、依赖注入、按拓扑顺序执行
    configure/init/startup/shutdown。

    Auto-injected base for @module-decorated classes.

    Orchestrates child service lifecycle — instantiation, DI wiring,
    configure/init/startup/shutdown in topological order.
    """

    def __init__(self) -> None:
        """初始化ModuleBase实例。

        Initializes the ModuleBase instance.
        """
        super().__init__()
        self._cf_parent_registry: Registry | None = None
        self._cf_registry: Registry | None = None
        self._cf_startup_order: list[str] = []
        self._cf_asgi_app: StarletteRouter | None = None

    @override
    async def configure(self, config_instance: object = None) -> None:
        """配置模块及其所有子服务。

        设置配置实例，创建注册表，注册所有服务及其依赖，
        执行拓扑排序，实例化服务，注入依赖，然后调用每个服务的configure方法。

        Args:
            config_instance: 配置对象实例。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Configure the module and all its child services.

        Sets the config instance, creates registry, registers all services and
        their dependencies, performs topological sort, instantiates services,
        injects dependencies, and calls configure on each service.

        Args:
            config_instance: The configuration object instance.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        self.config = config_instance

        meta = get_module_meta(type(self))
        if not meta.services:
            await self._invoke_hook(LifecycleHook.AFTER_CONFIG)
            return

        parent_registry = getattr(self, "_cf_parent_registry", None)
        registry = Registry(parent=parent_registry)
        self._cf_registry = registry

        for sub_cls in meta.services:
            self._register_entry_with_deps(sub_cls, registry)

        self._cf_startup_order = topological_sort(registry)

        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            entry.instance = entry.cls()

        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            inst = entry.instance
            if inst is None:
                raise DependencyInjectionError(f"Service '{name}' instance is None during wiring.")
            inject_deps(inst, entry, registry)
            if isinstance(inst, ModuleBase):
                inst._cf_parent_registry = registry
            setattr(self, to_snake(entry.cls.__name__), inst)

        for name in self._cf_startup_order:
            entry = registry.get_by_name(name)
            child = entry.instance
            if child is None:
                raise DependencyInjectionError(
                    f"Service '{name}' instance is None during configure."
                )
            await cast(LifecycleAware, child).configure(config_instance)

        await self._invoke_hook(LifecycleHook.AFTER_CONFIG)

    @override
    async def init(self) -> None:
        """初始化模块及其所有子服务。

        调用AFTER_INIT钩子，然后按拓扑顺序调用每个子服务的init方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Initialize the module and all its child services.

        Invokes the AFTER_INIT hook, then calls init on each child service
        in topological order.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        await self._invoke_hook(LifecycleHook.AFTER_INIT)
        registry = self._cf_registry
        if registry is not None:
            for name in self._cf_startup_order:
                child = registry.get_by_name(name).instance
                if child is None:
                    raise DependencyInjectionError(
                        f"Service '{name}' instance is None during init."
                    )
                await cast(LifecycleAware, child).init()

    @property
    def asgi_app(self) -> StarletteRouter:
        """获取ASGI应用。

        懒加载创建Starlette路由器，挂载所有具有asgi_app属性的子服务。

        Returns:
            StarletteRouter实例，包含所有子路由器的挂载点。

        Get the ASGI application.

        Lazily creates the Starlette router with mounts for all child services
        that have an asgi_app attribute.

        Returns:
            StarletteRouter instance with mounts for child routers.
        """
        if self._cf_asgi_app is None:
            routes: list[Mount] = []
            registry = self._cf_registry
            if registry is not None:
                for name in self._cf_startup_order:
                    entry = registry.get_by_name(name)
                    inst = entry.instance
                    asgi = getattr(inst, "asgi_app", None)
                    if asgi is not None:
                        app = cast(ASGIApp, asgi)
                        routes.append(Mount(f"/{name}", app=app))
            self._cf_asgi_app = StarletteRouter(routes)
        assert self._cf_asgi_app is not None
        return self._cf_asgi_app

    @override
    async def startup(self) -> None:
        """启动模块及其所有子服务。

        调用BEFORE_STARTUP钩子，然后按拓扑顺序调用每个子服务的startup方法。

        Raises:
            DependencyInjectionError: 如果服务实例为None。

        Start the module and all its child services.

        Invokes the BEFORE_STARTUP hook, then calls startup on each child service
        in topological order.

        Raises:
            DependencyInjectionError: If a service instance is None.
        """
        await self._invoke_hook(LifecycleHook.BEFORE_STARTUP)
        registry = self._cf_registry
        if registry is not None:
            for name in self._cf_startup_order:
                child = registry.get_by_name(name).instance
                if child is None:
                    raise DependencyInjectionError(
                        f"Service '{name}' instance is None during startup."
                    )
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
            DependencyInjectionError: If a service instance is None.
        """
        await self._invoke_hook(LifecycleHook.BEFORE_SHUTDOWN)
        registry = self._cf_registry
        if registry is not None:
            for name in reversed(self._cf_startup_order):
                child = registry.get_by_name(name).instance
                if child is None:
                    raise DependencyInjectionError(
                        f"Service '{name}' instance is None during shutdown."
                    )
                await cast(LifecycleAware, child).shutdown()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI应用入口点。

        如果是生命周期请求，则处理startup/shutdown；否则委托给asgi_app。

        Args:
            scope: ASGI scope字典。
            receive: 接收消息的异步函数。
            send: 发送消息的异步函数。

        ASGI application entry point.

        Handles startup/shutdown for lifecycle requests, otherwise delegates
        to the asgi_app.

        Args:
            scope: ASGI scope dictionary.
            receive: Async function to receive messages.
            send: Async function to send messages.
        """
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        else:
            await self.asgi_app(scope, receive, send)

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        """处理ASGI生命周期协议。

        监听startup和shutdown消息，并调用相应的方法。

        Args:
            receive: 接收消息的异步函数。
            send: 发送消息的异步函数。

        Handle ASGI lifespan protocol.

        Listens for startup and shutdown messages and calls the appropriate methods.

        Args:
            receive: Async function to receive messages.
            send: Async function to send messages.
        """
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await self.startup()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                return

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
        parent = registry.parent
        if parent is not None and parent.has(cls):
            return

        if is_cf_module(cls):
            mod_meta = get_module_meta(cls)
            registry.register(cls, meta=mod_meta)
            for dep in mod_meta.deps:
                self._register_entry_with_deps(dep, registry)
            return

        if is_cf_service(cls):
            svc_meta = get_service_meta(cls)
            registry.register(cls, meta=svc_meta)
            for dep in svc_meta.deps:
                self._register_entry_with_deps(dep, registry)
            return

        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")


__all__ = ["ModuleBase"]
