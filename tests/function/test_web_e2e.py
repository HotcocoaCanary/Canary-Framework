"""End-to-end HTTP tests for WebCanary.

Tests:
    - Start a real FastAPI+Uvicorn server and make HTTP requests
    - Verify routes are registered correctly
    - Verify config injection in web context
    - Verify lifecycle hooks fire
    - Verify error responses
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest

pytest.importorskip("fastapi", reason="fastapi required for WebCanary tests")
pytest.importorskip("uvicorn", reason="uvicorn required for WebCanary tests")


@pytest.mark.functional
class TestWebCanaryE2EBasic:
    """Basic end-to-end HTTP tests with a real server."""

    async def test_health_endpoint(self) -> None:
        """Start a WebCanary server, make a GET request, verify response."""
        from pydantic import BaseModel

        from canary_framework import config, module
        from canary_framework.web.fastapi import WebCanary, get, router

        @config
        class AppConfig(BaseModel):
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 18800

        @router(prefix="/api", name="health-router")
        class HealthRouter:
            @get("/health")
            async def health(self) -> dict[str, str]:
                return {"status": "ok"}

        @module("AppMod", services=[HealthRouter])
        class AppMod:
            pass

        app = WebCanary(AppMod)
        await app.config(config=AppConfig())
        await app.init()

        server_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.2)

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:18800/api/health")
                assert resp.status_code == 200
                assert resp.json() == {"status": "ok"}
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task
            await asyncio.sleep(0.1)

    async def test_multiple_routes(self) -> None:
        """Multiple GET/POST routes on different prefixes."""
        from pydantic import BaseModel

        from canary_framework import config, module
        from canary_framework.web.fastapi import WebCanary, get, post, router

        @config
        class AppConfig(BaseModel):
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 18801

        @router(prefix="/users", name="user-router")
        class UserRouter:
            @get("/")
            async def list(self) -> list[str]:
                return []

            @post("/")
            async def create(self) -> dict[str, str]:
                return {"id": "1"}

        @router(prefix="/items", name="item-router")
        class ItemRouter:
            @get("/{item_id}")
            async def get_item(self, item_id: str) -> dict[str, str]:
                return {"item": item_id}

        @module("AppMod", services=[UserRouter, ItemRouter])
        class AppMod:
            pass

        app = WebCanary(AppMod)
        await app.config(config=AppConfig())
        await app.init()

        server_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.2)

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                r1 = await client.get("http://127.0.0.1:18801/users/")
                assert r1.status_code == 200
                assert r1.json() == []

                r2 = await client.post("http://127.0.0.1:18801/users/")
                assert r2.status_code == 200
                assert r2.json() == {"id": "1"}

                r3 = await client.get("http://127.0.0.1:18801/items/42")
                assert r3.status_code == 200
                assert r3.json() == {"item": "42"}
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task
            await asyncio.sleep(0.1)

    async def test_404_on_unknown_route(self) -> None:
        """Unknown routes return 404."""
        from pydantic import BaseModel

        from canary_framework import config, module
        from canary_framework.web.fastapi import WebCanary, get, router

        @config
        class AppConfig(BaseModel):
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 18802

        @router(prefix="/api", name="test-router")
        class TRouter:
            @get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"msg": "hi"}

        @module("AppMod", services=[TRouter])
        class AppMod:
            pass

        app = WebCanary(AppMod)
        await app.config(config=AppConfig())
        await app.init()

        server_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.2)

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:18802/api/nonexistent")
                assert resp.status_code == 404
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task
            await asyncio.sleep(0.1)


@pytest.mark.functional
class TestWebCanaryLifecycle:
    """Verify lifecycle hooks fire correctly in WebCanary context."""

    async def test_lifecycle_hooks_in_router(self) -> None:
        """Router services should support lifecycle hooks like any service."""
        from pydantic import BaseModel

        from canary_framework import config, module, on_config, on_init, on_start
        from canary_framework.web.fastapi import WebCanary, get, router

        hooks_fired: list[str] = []

        @config
        class AppConfig(BaseModel):
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 18803

        @router(prefix="/api", name="hook-router")
        class HookRouter:
            @on_config
            def setup(self) -> None:
                hooks_fired.append("config")

            @on_init
            def init(self) -> None:
                hooks_fired.append("init")

            @on_start
            def start(self) -> None:
                hooks_fired.append("start")

            @get("/status")
            async def status(self) -> dict[str, str]:
                return {"hooks": str(hooks_fired)}

        @module("AppMod", services=[HookRouter])
        class AppMod:
            pass

        app = WebCanary(AppMod)
        await app.config(config=AppConfig())

        assert hooks_fired == ["config"]
        await app.init()
        assert hooks_fired == ["config", "init"]

        server_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.2)

        try:
            # start() internally triggers init → start lifecycle
            assert hooks_fired == ["config", "init", "start"]

            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:18803/api/status")
                assert resp.status_code == 200
                assert resp.json() == {"hooks": "['config', 'init', 'start']"}
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task
            await asyncio.sleep(0.1)

    async def test_config_injection_in_web_service(self) -> None:
        """Config fields should be accessible via self.config on services."""
        from pydantic import BaseModel

        from canary_framework import config, module, on_config, service
        from canary_framework.web.fastapi import WebCanary, get, router

        @config
        class AppConfig(BaseModel):
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 18804
            conn: str = "postgresql://test/db"

        @service("dbservice")
        class DBService:
            @on_config
            def setup(self) -> None:
                pass

            def get_conn(self) -> str:
                return self.config.conn  # type: ignore[attr-defined,no-any-return]

        @router(prefix="/api", name="cf-router", deps=[DBService])
        class CFRouter:
            db_service: DBService

            @get("/conn")
            async def conn(self) -> dict[str, str]:
                return {"conn": self.db_service.get_conn()}

        @module("AppMod", services=[DBService, CFRouter])
        class AppMod:
            pass

        app = WebCanary(AppMod)
        await app.config(config=AppConfig())
        await app.init()

        server_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.2)

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:18804/api/conn")
                assert resp.status_code == 200
                assert resp.json() == {"conn": "postgresql://test/db"}
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task
            await asyncio.sleep(0.1)


@pytest.mark.functional
class TestWebCanaryPrefixValidation:
    """Verify WebCanary handles router prefix edge cases gracefully."""

    async def test_trailing_slash_in_router_prefix(self) -> None:
        """A prefix ending with '/' should be trimmed (FastAPI rejects trailing slashes)."""
        from pydantic import BaseModel

        from canary_framework import config, module
        from canary_framework.web.fastapi import WebCanary, get, router

        @config
        class AppConfig(BaseModel):
            uvicorn_host: str = "127.0.0.1"
            uvicorn_port: int = 18805

        @router(prefix="/api/v1", name="prefix-router")
        class PrefixRouter:
            @get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"msg": "ok"}

        @module("AppMod", services=[PrefixRouter])
        class AppMod:
            pass

        app = WebCanary(AppMod)
        await app.config(config=AppConfig())
        await app.init()

        server_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.2)

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:18805/api/v1/hello")
                assert resp.status_code == 200
                assert resp.json() == {"msg": "ok"}
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task
            await asyncio.sleep(0.1)
