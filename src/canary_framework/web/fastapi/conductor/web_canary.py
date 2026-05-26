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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

from canary_framework.common._logging import get_logger
from canary_framework.common._types import RouterMeta
from canary_framework.core.conductor.canary import Canary
from canary_framework.core.container.registry import Registry
from canary_framework.core.decorators.service import get_service_meta
from canary_framework.web.fastapi.decorators.router import (
    get_route_info,
    is_route_method,
)

_UVICORN_PREFIX = "uvicorn_"
_FASTAPI_PREFIX = "fastapi_"

_log = get_logger("web")


# uvicorn 访问日志配置 — 使用 CF 风格格式，零中间件开销
_CF_ACCESS_LOG_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "cf_access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '[CF] [%(levelname)-5s] [cf.web] %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "cf_access": {
            "class": "logging.StreamHandler",
            "formatter": "cf_access",
        },
    },
    "loggers": {
        "uvicorn.access": {
            "handlers": ["cf_access"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


class WebCanary(Canary):
    """Canary variant that boots a FastAPI application via Uvicorn.

    继承 Canary，仅重写 ``start()`` 以启动 FastAPI + Uvicorn 服务器。

    Usage::

        @config
        class AppConfig:
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 8000
            fastapi_title: str = "My API"

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
        2. 构建 FastAPI lifespan 绑定 config → init → start → stop 生命周期
        3. 注册所有 @router 路由（使用 APIRouter + include_router）
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

        root_config = self.config_model

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

        host: str = uvicorn_kwargs.pop("host", "127.0.0.1")
        port: int = uvicorn_kwargs.pop("port", 8000)

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            """FastAPI lifespan: 绑定框架生命周期到 HTTP 服务器生命周期。"""
            await self.init()
            await Canary.start(self)
            app.state.cf_registry = self.registry
            _register_routes(app, self.registry)
            _log.info("FastAPI ready — listening on %s:%d", host, port)
            yield
            _log.info("Shutting down…")
            await self.stop()

        fastapi_app = FastAPI(lifespan=lifespan, **fastapi_kwargs)

        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            access_log=True,
            log_config=_CF_ACCESS_LOG_CONFIG,
            **uvicorn_kwargs,
        )
        server = uvicorn.Server(config)
        await server.serve()


# ============================================================================
# 内部路由注册 (Internal route registration)
# ============================================================================


def _register_routes(app: FastAPI, registry: Registry) -> None:
    """Scan all ``@router``-decorated entries and register their HTTP routes.

    遍历 registry 中所有 entry，筛选 ``RouterMeta``，为每个 router 创建
    FastAPI 原生 ``APIRouter``，通过 ``include_router`` 注册。
    prefix 拼接和 tags 合并由 FastAPI 处理，无需手动操作。
    """
    from fastapi import APIRouter

    for entry in registry.all_entries():
        meta = get_service_meta(entry.cls)
        if not isinstance(meta, RouterMeta):
            continue

        api_router = APIRouter(prefix=meta.prefix, tags=meta.tags)  # type: ignore[arg-type]

        for _, method in inspect.getmembers(entry.cls, inspect.isfunction):
            if not is_route_method(method):
                continue
            http_method, path, kwargs = get_route_info(method)
            bound = getattr(entry.instance, method.__name__)
            api_router.add_api_route(
                path=path,
                endpoint=bound,
                methods=[http_method],
                **kwargs,
            )

        app.include_router(api_router)
