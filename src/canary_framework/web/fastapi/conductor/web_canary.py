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
    根模块的 config 实例通过 ``self.config`` 访问，部分字段按前缀路由：

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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

from canary_framework.common._logging import get_logger
from canary_framework.core.conductor.canary import Canary
from canary_framework.web.fastapi.container import register_routes

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

    继承 Canary，分三阶段扩展核心生命周期：

    - ``config()`` — 核心 wiring + 按前缀拆分 uvicorn / fastapi 配置
    - ``init()``   — 核心 on_init 钩子 + 构建 FastAPI app + 注册路由
    - ``start()``  — 核心 on_start 钩子（lifespan）+ 启动 uvicorn，阻塞直到停止

    Usage::

        @module(name="AppModule", services=[...])
        class AppModule:
            ...

        app = WebCanary(AppModule)
        await app.config(config=AppConfig())
        await app.init()
        await app.start()  # 阻塞直到服务器停止
    """

    __slots__ = ("_fastapi_app", "_fastapi_kwargs", "_host", "_port", "_uvicorn_kwargs")

    def __init__(self, target: type) -> None:
        super().__init__(target)
        self._fastapi_kwargs: dict[str, Any] = {}
        self._uvicorn_kwargs: dict[str, Any] = {}
        self._host: str = "127.0.0.1"
        self._port: int = 8000
        self._fastapi_app: FastAPI | None = None

    # ==================================================================
    # 公开生命周期 (Public lifecycle)
    # ==================================================================

    async def config(self, *, config: Any = None) -> None:
        """Core wiring + web-config parsing.

        先执行 Canary 核心的收集 / 校验 / 排序 / wiring / on_config，
        再按 ``uvicorn_*`` / ``fastapi_*`` 前缀从根配置中拆分 web 参数。
        """
        await super().config(config=config)
        root_config = self.config_model
        if root_config is None:
            return

        for key, value in vars(root_config).items():
            if key.startswith("_"):
                continue
            if key.startswith(_UVICORN_PREFIX):
                self._uvicorn_kwargs[key[len(_UVICORN_PREFIX) :]] = value
            elif key.startswith(_FASTAPI_PREFIX):
                self._fastapi_kwargs[key[len(_FASTAPI_PREFIX) :]] = value

        self._host = self._uvicorn_kwargs.pop("host", "127.0.0.1")
        self._port = self._uvicorn_kwargs.pop("port", 8000)

    async def init(self) -> None:
        """Core on_init hooks + FastAPI app construction + route registration.

        先执行核心 on_init 钩子（连接池等初始化），
        再构建 FastAPI 应用并注册所有 @router 路由。"""
        try:
            import fastapi  # noqa: F401
        except ImportError:
            raise ImportError(
                "WebCanary requires FastAPI. Install it with: pip install canary-framework[web]"
            ) from None
        try:
            import uvicorn  # noqa: F401
        except ImportError:
            raise ImportError(
                "WebCanary requires Uvicorn. Install it with: pip install canary-framework[web]"
            ) from None

        await super().init()
        self._build_fastapi()
        # 路由注册须在实例 wiring 完成之后（init 阶段实例已就绪）
        register_routes(self._fastapi_app, self.registry)  # type: ignore[arg-type]

    async def start(self) -> None:
        """Start the FastAPI + Uvicorn server (blocking).

        启动 HTTP 服务器，阻塞直到收到停止信号。
        FastAPI lifespan 会在服务器启动 / 关闭时自动触发 on_start / on_end 钩子。
        """
        import uvicorn

        app = self._fastapi_app
        assert app is not None, "init() must be called before start()"
        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            access_log=True,
            log_config=_CF_ACCESS_LOG_CONFIG,
            **self._uvicorn_kwargs,
        )
        server = uvicorn.Server(config)
        await server.serve()

    # ==================================================================
    # Web wiring (framework-only)
    # ==================================================================
    def _build_fastapi(self) -> None:
        """Build a FastAPI application with lifespan, store on ``_fastapi_app``.

        构建 FastAPI 应用，注入 lifespan 将框架生命周期绑定到 HTTP 服务器生命周期。
        lifespan 在服务器启动时调用 ``Canary.start(self)``（on_start 钩子），
        在服务器关闭时调用 ``self.stop()``（on_end 钩子逆序）。
        """
        from fastapi import FastAPI

        _self = self

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            """Lifespan — bridges Canary lifecycle hooks to HTTP server lifecycle."""
            await Canary.start(_self)
            app.state.cf_registry = _self.registry
            _log.info("FastAPI ready — listening on %s:%d", _self._host, _self._port)
            yield
            _log.info("Shutting down…")
            await _self.stop()

        self._fastapi_app = FastAPI(lifespan=lifespan, **self._fastapi_kwargs)
