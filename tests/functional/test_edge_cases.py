"""Functional tests for edge cases, error scenarios, and boundary conditions."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


class _NotDecorated:
    pass


class _SomeDep:
    pass


@pytest.mark.functional
class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    # ── Undecorated class ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_undecorated_in_module_raises(self) -> None:
        """Undecorated class in module services raises TypeError."""

        @service()
        class ValidService(ServiceBase):
            pass

        with pytest.raises(TypeError, match="not decorated"):

            @module(services=[ValidService, _NotDecorated])
            class _TestModule(ModuleBase):
                pass

    # ── DI: missing dependency standalone ──────────────────────────

    @pytest.mark.asyncio
    async def test_service_missing_di(self) -> None:
        """Service with unresolved DI — starts but attribute is None when not in module."""

        @service()
        class ServiceWithDep(ServiceBase):
            missing_dep: _SomeDep

        app = ServiceWithDep()
        app.init()
        assert getattr(app, "missing_dep", None) is None

    # ── Boolean query param edge cases ─────────────────────────────

    @pytest.mark.asyncio
    async def test_bool_query_param_true_values(self) -> None:
        """Boolean query params — only "true" (case-insensitive) is True, everything else False."""

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.get("/check")
            async def check(self, flag: bool) -> dict[str, bool]:
                return {"flag": flag}

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for val in ("true", "True", "TRUE", "tRuE"):
                r = await client.get(f"/check?flag={val}")
                assert r.json()["flag"] is True, f"'{val}' should be True"

            for val in ("false", "False", "0", "1", "yes", "no", "on", "off", "", "anything"):
                r = await client.get(f"/check?flag={val}")
                assert r.json()["flag"] is False, f"'{val}' should be False"

    # ── Empty path handling ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_service_root_path(self) -> None:
        """Service with root path '/'."""

        @service()
        class RootService(ServiceBase):
            router = Router()

            @router.get("/")
            async def root(self) -> dict[str, str]:
                return {"home": "yes"}

        app = RootService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/")
            assert r.status_code == 200
            assert r.json() == {"home": "yes"}

    # ── Multiple HTTP methods on same path ─────────────────────────

    @pytest.mark.asyncio
    async def test_multiple_methods_same_path(self) -> None:
        """GET and POST on same path both work."""

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.get("/item")
            async def get_item(self) -> dict[str, str]:
                return {"method": "get"}

            @router.post("/item")
            async def post_item(self) -> dict[str, str]:
                return {"method": "post"}

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/item")
            assert r.json() == {"method": "get"}
            r = await client.post("/item")
            assert r.json() == {"method": "post"}

    # ── Router prefix edge cases ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_router_prefix_trailing_slash_openapi(self) -> None:
        """Router prefix with trailing slash — OpenAPI normalizes double slashes."""

        @service()
        class MyService(ServiceBase):
            router = Router(prefix="/api/")

            @router.get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"ok": "yes"}

        app = MyService()
        app.init()
        await app.startup()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/openapi.json")
            assert r.status_code == 200
            schema = r.json()
            paths = schema.get("paths", {})
            assert "/api/hello" in paths
            assert "/api//hello" not in paths

    @pytest.mark.asyncio
    async def test_router_prefix_sets_mount_path(self) -> None:
        """Router prefix controls mount path in module context."""

        @service()
        class MyService(ServiceBase):
            router = Router(prefix="/custom")

            @router.get("/test")
            async def test(self) -> dict[str, str]:
                return {"ok": "yes"}

        @module(services=[MyService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/custom/test")
            assert r.status_code == 200

    # ── Swagger and ReDoc docs ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_swagger_and_redoc_available(self) -> None:
        """Both Swagger UI and ReDoc are available after startup."""

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.get("/test")
            async def test(self) -> dict[str, str]:
                return {"ok": "yes"}

        app = MyService()
        app.init()
        await app.startup()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/docs")
            assert r.status_code == 200
            assert "swagger" in r.text.lower()

            r = await client.get("/redoc")
            assert r.status_code == 200
            assert "redoc" in r.text.lower()

    # ── Deep nesting stress ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_deeply_nested_module(self) -> None:
        """Deeply nested module chain — all routes resolve."""

        @service()
        class LeafService(ServiceBase):
            router = Router()

            @router.get("/data")
            async def data(self) -> dict[str, str]:
                return {"depth": "leaf"}

        @module(services=[LeafService])
        class Level3(ModuleBase):
            pass

        @module(services=[Level3])
        class Level2(ModuleBase):
            pass

        @module(services=[Level2])
        class Level1(ModuleBase):
            pass

        app = Level1()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/Level2/Level3/LeafService/data")
            assert r.status_code == 200
            assert r.json() == {"depth": "leaf"}

    # ── return types (str, dict, list, BaseModel) ──────────────────

    @pytest.mark.asyncio
    async def test_return_types(self) -> None:
        """Various return types are handled correctly."""

        class Item(BaseModel):
            name: str

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.get("/str")
            async def str_route(self) -> str:
                return "plain text"

            @router.get("/dict")
            async def dict_route(self) -> dict[str, int]:
                return {"a": 1}

            @router.get("/list")
            async def list_route(self) -> list[int]:
                return [1, 2, 3]

            @router.get("/model", response_model=Item)
            async def model_route(self) -> Item:
                return Item(name="test")

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/str")
            assert r.text == "plain text"

            r = await client.get("/dict")
            assert r.json() == {"a": 1}

            r = await client.get("/list")
            assert r.json() == [1, 2, 3]

            r = await client.get("/model")
            assert r.json()["name"] == "test"
