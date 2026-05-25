"""Web engine — extends :class:`Canary` for FastAPI + Uvicorn integration.

设计思路 (Design rationale):
    为什么 FastAPI 集成放在 ``web/`` 下作为"插件"而非核心？
    （Why is FastAPI a plugin under ``web/`` and not in core?）

    1. **可选依赖**：并非所有用户都需要 Web 层，拆分后核心库保持轻量
       Core remains lightweight; ``pip install canary-framework[web]``
       adds FastAPI support.
    2. **多框架扩展**：``web/fastapi/conductor/web_canary.py`` 只实现一个
       ``start()``，未来 ``web/litestar/`` 可以同样覆写
       Multi-framework: each integration just overrides ``start()``.
    3. **职责分离**：核心负责生命周期，Web 层负责 HTTP 暴露
       Separation of concerns: core handles lifecycle, web handles HTTP.

配置前缀约定 (Config prefix convention):
    根模块的 ``@config`` 类通过前缀区分参数归属:

        =================  ===========================  =========================
        Prefix             Consumer                     Example field
        =================  ===========================  =========================
        ``uvicorn_*``      ``uvicorn.Config``           ``uvicorn_host``
        ``fastapi_*``      ``FastAPI()``                ``fastapi_title``
        (no prefix)        Business config (untouched)  ``database_url``
        =================  ===========================  =========================

安全默认值 (Safe defaults):
    ``uvicorn_host`` 默认 ``127.0.0.1``（而非 ``0.0.0.0``），避免
    新项目暴露到公网。上线时用户显式修改即可。
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

from canary_framework.core.conductor.canary import Canary
from canary_framework.core.container.registry import Registry
from canary_framework.core.decorators.module import is_cf_module
from canary_framework.core.decorators.service import is_cf_service
from canary_framework.web.fastapi.decorators.router import (
    get_route_info,
    get_router_prefix,
    is_route_method,
)
from canary_framework.web.fastapi.decorators.web import get_web_routers, is_web

_UVICORN_PREFIX = "uvicorn_"
_FASTAPI_PREFIX = "fastapi_"

_log = logging.getLogger("cf.web")


class WebCanary(Canary):
    """Canary variant that boots a FastAPI application via Uvicorn.

    继承 Canary，仅重写 ``start()`` 以启动 FastAPI + Uvicorn 服务器。

    Usage::

        @config
        class AppConfig:
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 8000
            fastapi_title: str = "My API"

        @web()
        @module(name="AppModule", config=AppConfig, services=[...])
        class AppModule:
            ...

        app = WebCanary(AppModule)
        await app.init()
        await app.start()  # 阻塞直到服务器停止
    """

    async def start(self) -> None:
        """Start the FastAPI + Uvicorn server.

        1. 从根模块 config 按前缀拆分参数
        2. 构建 FastAPI lifespan 绑定框架的 on_start / on_end
        3. 注册所有 @web 路由
        4. 启动 uvicorn.Server.serve()（阻塞直到收到停止信号）

        Raises:
            ImportError: 未安装 fastapi/uvicorn。
                ``pip install canary-framework[web]``
        """
        try:
            from fastapi import FastAPI
        except ImportError:
            raise ImportError(
                "WebCanary requires FastAPI. Install it with: pip install canary-framework[web]"
            ) from None
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "WebCanary requires Uvicorn. Install it with: pip install canary-framework[web]"
            ) from None

        root_entry = self.registry.get_by_class(self._target)
        root_config = root_entry.config_instance

        # 按前缀拆分参数
        # Split config fields by prefix
        uvicorn_kwargs: dict[str, Any] = {}
        fastapi_kwargs: dict[str, Any] = {}

        if root_config is not None:
            for key, value in vars(root_config).items():
                if key.startswith("_"):
                    continue  # 跳过私有字段
                if key.startswith(_UVICORN_PREFIX):
                    uvicorn_kwargs[key[len(_UVICORN_PREFIX) :]] = value
                elif key.startswith(_FASTAPI_PREFIX):
                    fastapi_kwargs[key[len(_FASTAPI_PREFIX) :]] = value

        # 安全默认值：绑定 localhost
        host: str = uvicorn_kwargs.pop("host", "127.0.0.1")
        port: int = uvicorn_kwargs.pop("port", 8000)

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            """FastAPI lifespan: 绑定框架生命周期到 HTTP 服务器生命周期。"""
            await Canary.start(self)
            app.state.cf_registry = self.registry
            _register_routes(app, self.registry)
            _log.info("FastAPI ready — listening on %s:%d", host, port)
            yield
            _log.info("Shutting down…")
            await self.stop()

        fastapi_app = FastAPI(lifespan=lifespan, **fastapi_kwargs)

        config = uvicorn.Config(fastapi_app, host=host, port=port, **uvicorn_kwargs)
        server = uvicorn.Server(config)
        await server.serve()


# ============================================================================
# 内部路由注册 (Internal route registration)
# ============================================================================


def _register_routes(app: FastAPI, registry: Registry) -> None:
    """Scan all ``@web``-marked entries and register their HTTP routes.

    扫描所有 @web 标记的服务/模块，将其路由注册到 FastAPI。

    三种注册场景 (Three scenarios):
        1. 外部路由类: ``@web(routers=[UserRouter])`` → 注册每个 Router 的方法
        2. 自身方法: 无 routers 但类自身有 ``@get``/``@post`` 方法
        3. 混合: 既有 routers 又是 @module → 同时注册
    """
    for entry in registry.all_entries():
        cls = entry.cls
        if not is_web(cls):
            continue

        routers = get_web_routers(cls)

        # 1. 外部路由类
        for router_cls in routers:
            prefix = get_router_prefix(router_cls)
            ctx = entry.context
            if ctx is None:
                _log.warning(
                    "Context is None for '%s' — skipping router '%s'",
                    entry.name,
                    router_cls.__name__,
                )
                continue
            router_instance = router_cls(ctx)
            _register_instance_routes(app, router_instance, prefix)

        owns_routers = bool(routers)
        is_container = is_cf_module(cls) or is_cf_service(cls)

        # 2. 自身方法（无外部 routers）
        if not owns_routers and is_container:
            _register_instance_routes(app, entry.instance, "")

        # 3. 混合：有 routers 的模块同时注册自身方法
        if owns_routers and is_cf_module(cls):
            _register_instance_routes(app, entry.instance, "")


def _register_instance_routes(
    app: FastAPI,
    instance: object,
    prefix: str,
) -> None:
    """Scan *instance* for ``@get`` / ``@post`` / … methods and register them.

    扫描实例类的 @get/@post/@put/@delete/@patch 方法，注册到 FastAPI。

    Args:
        app: FastAPI 应用实例。
        instance: 包含路由方法的类实例。
        prefix: URL 前缀，拼接到每个方法的路径前。
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
