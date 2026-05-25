"""Web 层启动引擎 —— 继承 Canary，接入 FastAPI + Uvicorn。

WebCanary 仅重写 start(): 从根模块 @config 按前缀提取参数并启动 HTTP 服务器。

配置前缀规则:
    uvicorn_* → uvicorn.Config / uvicorn.Server
    fastapi_* → FastAPI(kwargs)
    无前缀    → 业务配置，框架不触碰
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import Any

from cf import Canary
from cf.core.decorators.module import is_cf_module
from cf.core.decorators.service import is_cf_service
from cf.core.registry.registry import Registry
from cf.web.fastapi.decorators.router import get_route_info, get_router_prefix, is_route_method
from cf.web.fastapi.decorators.web import get_web_routers, is_web
from fastapi import FastAPI

_UVICORN_PREFIX = "uvicorn_"  # uvicorn_host → uvicorn.Config(host=...)
_FASTAPI_PREFIX = "fastapi_"  # fastapi_title → FastAPI(title=...)


class WebCanary(Canary):
    """Web 层引擎 —— 继承 Canary，仅重写 start() 以接入 FastAPI + Uvicorn。

    根模块的 @config 类字段按前缀分发给不同消费者:
        uvicorn_* → uvicorn.Config / uvicorn.Server 参数
        fastapi_* → FastAPI() 构造参数
        无前缀    → 业务配置（框架不触碰）

    Usage:
        @config
        class AppConfig:
            uvicorn_host: str = "0.0.0.0"
            uvicorn_port: int = 8000
            fastapi_title: str = "My API"

        app = WebCanary(MyRootModule)
        await app.init()
        await app.start()
    """

    async def start(self) -> None:
        """启动 FastAPI 服务器，通过 lifespan 绑定 Canary 生命周期。

        1. 从根模块 config 按前缀拆分参数到 uvicorn_kwargs 和 fastapi_kwargs
        2. 提取 host / port 用于 uvicorn
        3. FastAPI(lifespan=..., **fastapi_kwargs)
        4. uvicorn.Server.serve() 阻塞直到收到停止信号
        """
        root_entry = self.registry.get_by_class(self._target)
        root_config = root_entry.config_instance

        uvicorn_kwargs: dict[str, Any] = {}
        fastapi_kwargs: dict[str, Any] = {}

        if root_config is not None:
            for key, value in vars(root_config).items():
                if key.startswith("_"):
                    continue
                if key.startswith(_UVICORN_PREFIX):
                    uvicorn_kwargs[key[len(_UVICORN_PREFIX) :]] = value
                elif key.startswith(_FASTAPI_PREFIX):
                    fastapi_kwargs[key[len(_FASTAPI_PREFIX) :]] = value

        host = uvicorn_kwargs.pop("host", "0.0.0.0")
        port = uvicorn_kwargs.pop("port", 8000)

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """FastAPI lifespan: 服务器启动 → 注册路由 → 接收请求 → 停止。"""
            await Canary.start(self)  # 触发 on_start 钩子
            app.state.cf_registry = self.registry
            _register_routes(app, self.registry)
            yield  # 服务器就绪
            await self.stop()  # 触发 on_end 钩子

        fastapi_app = FastAPI(lifespan=lifespan, **fastapi_kwargs)

        import uvicorn

        config = uvicorn.Config(fastapi_app, host=host, port=port, **uvicorn_kwargs)
        server = uvicorn.Server(config)
        await server.serve()


def _register_routes(app: FastAPI, registry: Registry) -> None:
    """扫描所有 @web 标记的服务/模块，将其路由注册到 FastAPI 应用。

    三场景:
        1. 外部路由类: @web(routers=[UserRouter]) → 注册每个 Router 的 HTTP 方法
        2. 自身方法: 无 routers 但类自身有 @get/@post → 注册自身方法
        3. 混合: 既有 routers 又是 @module → 同时注册外部路由类 + 自身方法
    """
    for entry in registry.all_entries():
        cls = entry.cls
        if not is_web(cls):
            continue

        routers = get_web_routers(cls)

        # 外部路由类
        for router_cls in routers:
            prefix = get_router_prefix(router_cls)
            router_instance = router_cls(entry.context)
            _register_instance_routes(app, router_instance, prefix)

        # 自身方法（无外部 routers 时，或模块自身有额外方法时）
        if not routers and (is_cf_module(cls) or is_cf_service(cls)):
            _register_instance_routes(app, entry.instance, "")

        if routers and is_cf_module(cls):
            _register_instance_routes(app, entry.instance, "")


def _register_instance_routes(app: FastAPI, instance: object, prefix: str) -> None:
    """扫描实例类的 @get/@post/@put/@delete/@patch 方法，注册为 FastAPI 路由。

    Args:
        app: FastAPI 应用实例。
        instance: 包含路由方法的类实例。
        prefix: URL 前缀（如 "/api/users"），拼接到每个方法的路径前面。
    """
    for _, method in inspect.getmembers(instance.__class__, inspect.isfunction):
        if not is_route_method(method):
            continue

        http_method, path, kwargs = get_route_info(method)
        # 拼接 prefix + path，去除末尾多余斜杠
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
