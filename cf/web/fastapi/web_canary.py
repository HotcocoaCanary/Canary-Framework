# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from cf import Canary
from cf.core.decorators.module import is_cf_module
from cf.core.decorators.service import is_cf_service
from cf.core.registry.registry import Registry

from cf.web.fastapi.decorators.router import is_route_method, get_route_info, get_router_prefix
from cf.web.fastapi.decorators.web import is_web, get_web_routers


class WebCanary(Canary):
    # Web 层启动引擎：继承 Canary，仅重写 start() 以接入 FastAPI + Uvicorn
    # init() 和 stop() 直接复用父类，无需重写

    def __init__(
        self,
        target: type,
        *,
        fastapi_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(target)                   # 复用 Canary 全部初始化逻辑
        self._fastapi_kwargs = fastapi_kwargs or {}  # FastAPI 构造参数

    async def start(self) -> None:
        # 从根模块的配置读 host / port，无配置用默认值
        root_entry = self.registry.get_by_class(self._target)
        root_config = root_entry.config_instance
        host = getattr(root_config, "host", "0.0.0.0") if root_config else "0.0.0.0"
        port = getattr(root_config, "port", 8000) if root_config else 8000

        # lifespan：将 Canary 生命周期与 HTTP 服务器绑定
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await Canary.start(self)           # 父类 start：触发 on_start 钩子
            app.state.cf_registry = self.registry
            _register_routes(app, self.registry)
            yield
            await self.stop()                  # 父类 stop：触发 on_end 钩子

        fastapi_app = FastAPI(lifespan=lifespan, **self._fastapi_kwargs)

        import uvicorn
        config = uvicorn.Config(fastapi_app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()


def _register_routes(app: FastAPI, registry: Registry) -> None:
    for entry in registry.all_entries():
        cls = entry.cls

        if not is_web(cls):
            continue

        routers = get_web_routers(cls)

        for router_cls in routers:
            prefix = get_router_prefix(router_cls)
            router_instance = router_cls(entry.context)
            _register_instance_routes(app, router_instance, prefix)

        if not routers and (is_cf_module(cls) or is_cf_service(cls)):
            _register_instance_routes(app, entry.instance, "")

        if routers and is_cf_module(cls):
            _register_instance_routes(app, entry.instance, "")


def _register_instance_routes(app: FastAPI, instance: object, prefix: str) -> None:
    for _, method in inspect.getmembers(instance.__class__, inspect.isfunction):
        if not is_route_method(method):
            continue

        http_method, path, kwargs = get_route_info(method)
        full_path = prefix.rstrip("/") + "/" + path.lstrip("/")
        if full_path.endswith("/") and full_path != "/":
            full_path = full_path.rstrip("/")

        bound = getattr(instance, method.__name__)
        app.add_api_route(
            path=full_path,
            endpoint=bound,
            methods=[http_method],
            **kwargs,
        )
