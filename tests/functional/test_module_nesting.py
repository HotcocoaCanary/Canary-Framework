"""Functional tests for nested Module scenarios."""

import pytest
from httpx import ASGITransport, AsyncClient

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestModuleNesting:
    """Tests for nested Modules."""

    @pytest.mark.asyncio
    async def test_module_nesting_service(self) -> None:
        """Module → Service — routes propagate to root."""

        @service()
        class ApiService(ServiceBase):
            router = Router()

            @router.get("/data")
            async def get_data(self) -> dict[str, str]:
                return {"source": "leaf"}

        @module(services=[ApiService])
        class SubModule(ModuleBase):
            pass

        @module(services=[SubModule])
        class RootModule(ModuleBase):
            pass

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/SubModule/ApiService/data")
            assert response.status_code == 200
            assert response.json() == {"source": "leaf"}

            response = await client.get("/openapi.json")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_module_two_level_nesting(self) -> None:
        """Root → Mid → Service — three-level route propagation."""

        @service()
        class DeepService(ServiceBase):
            router = Router()

            @router.get("/deep")
            async def deep(self) -> dict[str, str]:
                return {"level": "deep"}

        @module(services=[DeepService])
        class MidModule(ModuleBase):
            pass

        @module(services=[MidModule])
        class RootModule(ModuleBase):
            pass

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/MidModule/DeepService/deep")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_module_nesting_multiple_services(self) -> None:
        """Module → multiple child Modules each with Services."""

        @service()
        class UserService(ServiceBase):
            router = Router()

            @router.get("/me")
            async def me(self) -> dict[str, str]:
                return {"user": "alice"}

        @service()
        class OrderService(ServiceBase):
            router = Router()

            @router.get("/mine")
            async def mine(self) -> dict[str, list[str]]:
                return {"orders": []}

        @module(services=[UserService])
        class UserModule(ModuleBase):
            pass

        @module(services=[OrderService])
        class OrderModule(ModuleBase):
            pass

        @module(services=[UserModule, OrderModule])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.get("/UserModule/UserService/me")
            assert r1.status_code == 200

            r2 = await client.get("/OrderModule/OrderService/mine")
            assert r2.status_code == 200

            schema = (await client.get("/openapi.json")).json()
            assert "/me" in schema["paths"]
            assert "/mine" in schema["paths"]

    @pytest.mark.asyncio
    async def test_module_nesting_with_di_across_modules(self) -> None:
        """DI across module boundaries: child module's service depends on root module's service."""

        @service()
        class SharedDB(ServiceBase):
            def query(self) -> str:
                return "shared-data"

        @service()
        class ConsumerService(ServiceBase):
            router = Router()
            db: SharedDB

            @router.get("/data")
            async def get_data(self) -> dict[str, str]:
                return {"data": self.db.query()}

        @module(services=[ConsumerService])
        class ChildModule(ModuleBase):
            pass

        @module(services=[SharedDB, ChildModule])
        class RootModule(ModuleBase):
            pass

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ChildModule/ConsumerService/data")
            assert response.status_code == 200
            assert response.json() == {"data": "shared-data"}

    @pytest.mark.asyncio
    async def test_module_nesting_empty_mid(self) -> None:
        """Root → empty Module → Service."""

        @service()
        class LeafService(ServiceBase):
            router = Router()

            @router.get("/leaf")
            async def leaf(self) -> dict[str, str]:
                return {"ok": "leaf"}

        @module(services=[])
        class MidModule(ModuleBase):
            pass

        @module(services=[MidModule, LeafService])
        class RootModule(ModuleBase):
            pass

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/LeafService/leaf")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_module_nesting_no_routes_in_any_service(self) -> None:
        """Nested modules with no routers anywhere — no docs."""

        @service()
        class DataService(ServiceBase):
            pass

        @module(services=[DataService])
        class SubModule(ModuleBase):
            pass

        @module(services=[SubModule])
        class RootModule(ModuleBase):
            pass

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                response = await client.get(path)
                assert response.status_code == 404, f"{path} should 404"
