from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from cf import Canary
from cf.core.decorators.module import is_cf_module
from cf.core.decorators.service import is_cf_service
from cf.core.registry.registry import Registry

from cf.web.fastapi.context import RouterContext
from cf.web.fastapi.decorators.router import is_route_method, get_route_info, get_router_prefix
from cf.web.fastapi.decorators.web import is_web, get_web_routers


class WebCanary:
    def __init__(
        self,
        target: type,
        *,
        config_file_path: str = ".env",
        log_level: str = "INFO",
        log_format: str = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        fastapi_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._target = target
        self._config_file_path = config_file_path
        self._log_level = log_level
        self._log_format = log_format
        self._fastapi_kwargs = fastapi_kwargs or {}
        self._canary: Canary | None = None

    def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        uvicorn_kwargs: dict[str, Any] | None = None,
    ) -> None:
        canary = Canary(
            self._target,
            config_file_path=self._config_file_path,
            log_level=self._log_level,
            log_format=self._log_format,
        )
        self._canary = canary

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await canary._startup()
            app.state.cf_registry = canary._registry
            _register_routes(app, canary._registry)
            yield
            await canary._shutdown()

        fastapi_app = FastAPI(lifespan=lifespan, **self._fastapi_kwargs)

        import uvicorn
        _uvicorn_kwargs = uvicorn_kwargs or {}
        uvicorn.run(fastapi_app, host=host, port=port, log_level=self._log_level.lower(), **_uvicorn_kwargs)

    def stop(self) -> None:
        if self._canary:
            self._canary.stop()


def _register_routes(app: FastAPI, registry: Registry) -> None:
    for entry in registry.all_entries():
        cls = entry.cls
        if not is_web(cls):
            continue

        routers = get_web_routers(cls)

        for router_cls in routers:
            prefix = get_router_prefix(router_cls)
            ctx = RouterContext(entry.instance, registry)
            router_instance = router_cls(ctx)
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
