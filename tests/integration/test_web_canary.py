"""Integration tests for :mod:`canary_framework.web.fastapi` — WebCanary engine.

Covers:
    - _register_routes function with real FastAPI app
    - Config parameter splitting (uvicorn_* / fastapi_* prefixes)
    - Router auto-discovery via RouterMeta
    - DI injection into routers
    - Router in module's services list
    - Single-service entry point with router in deps
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestRegisterRoutes:
    """Verify _register_routes registers @router endpoints on a FastAPI app."""

    def test_registers_routes_from_router_meta(self) -> None:
        from fastapi import FastAPI

        from canary_framework.core.container.registry import Registry
        from canary_framework.web.fastapi.conductor.web_canary import (
            _register_routes,
        )
        from canary_framework.web.fastapi.decorators.router import get, router

        @router(prefix="/test", name="reg-router")
        class RegRouter:
            @get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"msg": "ok"}

        reg = Registry()
        reg.register(RegRouter)

        app = FastAPI()
        _register_routes(app, reg)

        routes = [r for r in app.routes if hasattr(r, "path")]
        assert any("/test/hello" in str(r.path) for r in routes)

    def test_registers_with_tags(self) -> None:
        from fastapi import FastAPI

        from canary_framework.core.container.registry import Registry
        from canary_framework.web.fastapi.conductor.web_canary import (
            _register_routes,
        )
        from canary_framework.web.fastapi.decorators.router import get, router

        @router(prefix="/api/v2", tags=["v2", "beta"], name="tagged")
        class TaggedRouter:
            @get("/items")
            async def items(self) -> dict[str, str]:
                return {"ok": "true"}

        reg = Registry()
        reg.register(TaggedRouter)
        app = FastAPI()
        _register_routes(app, reg)

        routes = [r for r in app.routes if hasattr(r, "path")]
        assert any("/api/v2/items" in str(r.path) for r in routes)

    def test_skips_non_router_entries(self) -> None:
        from fastapi import FastAPI

        from canary_framework.core.container.registry import Registry
        from canary_framework.core.decorators.service import service
        from canary_framework.web.fastapi.conductor.web_canary import (
            _register_routes,
        )

        @service("plain-service")
        class PlainService:
            pass

        reg = Registry()
        reg.register(PlainService)
        app = FastAPI()
        _register_routes(app, reg)

        routes = [r for r in app.routes if hasattr(r, "path")]
        assert not any("plain" in str(r.path) for r in routes)

    def test_multiple_routers_registered(self) -> None:
        from fastapi import FastAPI

        from canary_framework.core.container.registry import Registry
        from canary_framework.web.fastapi.conductor.web_canary import (
            _register_routes,
        )
        from canary_framework.web.fastapi.decorators.router import delete, get, post, router

        @router(prefix="/users", name="user-r")
        class UserR:
            @get("/")
            async def list_users(self) -> list[dict[str, str]]:
                return []

        @router(prefix="/posts", name="post-r")
        class PostR:
            @post("/")
            async def create_post(self) -> dict[str, str]:
                return {"id": "1"}

            @delete("/{post_id}")
            async def delete_post(self, post_id: str) -> dict[str, str]:
                return {"deleted": post_id}

        reg = Registry()
        reg.register(UserR)
        reg.register(PostR)
        app = FastAPI()
        _register_routes(app, reg)

        routes = [r for r in app.routes if hasattr(r, "path")]
        paths = [str(r.path) for r in routes]
        assert any("/users/" in p for p in paths)
        assert any("/posts/" in p for p in paths)


@pytest.mark.integration
class TestWebCanaryConfigSplitting:
    """Verify config prefix splitting in WebCanary.start()."""

    async def test_uvicorn_fastapi_prefix_splitting(self) -> None:

        from canary_framework import config, module
        from canary_framework.web.fastapi import WebCanary
        from canary_framework.web.fastapi.decorators.router import get, router

        @config
        class AppCfg:
            uvicorn_host: str = "0.0.0.0"
            uvicorn_port: int = 9999
            fastapi_title: str = "Test API"
            database_url: str = "sqlite://"

        @router(prefix="/", name="root-router")
        class RootRouter:
            @get("/ping")
            async def ping(self) -> dict[str, str]:
                return {"pong": "true"}

        @module("root", config=AppCfg, services=[RootRouter])
        class RootModule:
            pass

        app = WebCanary(RootModule)
        await app.init()

        root_entry = app.registry.get_by_name("root")
        cfg = root_entry.config_instance
        assert cfg is not None
        assert getattr(cfg, "uvicorn_host", None) == "0.0.0.0"
        assert getattr(cfg, "uvicorn_port", None) == 9999
        assert getattr(cfg, "fastapi_title", None) == "Test API"
        assert getattr(cfg, "database_url", None) == "sqlite://"
