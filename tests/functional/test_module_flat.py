"""Functional tests for flat Module scenarios (no nesting)."""

import pytest
from httpx import ASGITransport, AsyncClient

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestModuleFlat:
    """Tests for Modules with direct child services (no nesting)."""

    @pytest.mark.asyncio
    async def test_module_empty(self) -> None:
        """Scenario 3a: Empty module — starts, no routes, docs 404."""

        @module(services=[])
        class EmptyModule(ModuleBase):
            pass

        app = EmptyModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/docs")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_module_with_service_no_router(self) -> None:
        """Scenario 3b: Module with one service (no router) — starts, no docs."""

        @service()
        class DataService(ServiceBase):
            pass

        @module(services=[DataService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/docs")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_module_with_one_router_service(self) -> None:
        """Scenario 4: Module with one Service that has a Router — routes work, docs available."""

        @service()
        class ApiService(ServiceBase):
            router = Router()

            @router.get("/ping")
            async def ping(self) -> dict[str, str]:
                return {"status": "ok"}

        @module(services=[ApiService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Route works
            response = await client.get("/ping")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            # Docs available
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "/ping" in schema["paths"]

    @pytest.mark.asyncio
    async def test_module_with_multiple_router_services(self) -> None:
        """Module with multiple router services — all routes work, one OpenAPI."""

        @service()
        class UserService(ServiceBase):
            router = Router(prefix="/users")

            @router.get("/list")
            async def list_users(self) -> dict[str, list[str]]:
                return {"users": []}

        @service()
        class OrderService(ServiceBase):
            router = Router(prefix="/orders")

            @router.get("/list")
            async def list_orders(self) -> dict[str, list[str]]:
                return {"orders": []}

        @module(services=[UserService, OrderService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Both routes work
            response = await client.get("/users/list")
            assert response.status_code == 200
            response = await client.get("/orders/list")
            assert response.status_code == 200

            # One OpenAPI doc covers both
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "/users/list" in schema["paths"]
            assert "/orders/list" in schema["paths"]

    @pytest.mark.asyncio
    async def test_module_with_di_between_services(self) -> None:
        """Module with DI: one service depends on another."""

        @service()
        class CounterService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.count = 0

            def increment(self) -> int:
                self.count += 1
                return self.count

        @service()
        class ApiService(ServiceBase):
            router = Router()
            counter: CounterService  # DI

            @router.get("/count")
            async def get_count(self) -> dict[str, int]:
                return {"count": self.counter.increment()}

        @module(services=[ApiService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/count")
            assert response.status_code == 200
            assert response.json()["count"] == 1

            response = await client.get("/count")
            assert response.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_module_service_with_optional_di(self) -> None:
        """Module with Optional[Service] DI — resolves correctly."""

        @service()
        class OptionalDepService(ServiceBase):
            pass

        @service()
        class ApiService(ServiceBase):
            router = Router()
            dep: OptionalDepService | None

            @router.get("/has-dep")
            async def has_dep(self) -> dict[str, bool]:
                return {"has_dep": self.dep is not None}

        @module(services=[OptionalDepService, ApiService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/has-dep")
            assert response.status_code == 200
            assert response.json()["has_dep"] is True

    @pytest.mark.asyncio
    async def test_module_service_discovery_via_di(self) -> None:
        """Services declared via DI annotation auto-registered."""

        @service()
        class HelperService(ServiceBase):
            def value(self) -> int:
                return 99

        @service()
        class MainService(ServiceBase):
            router = Router()
            helper: HelperService  # auto-registers HelperService

            @router.get("/val")
            async def get_val(self) -> dict[str, int]:
                return {"val": self.helper.value()}

        @module(services=[MainService])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/val")
            assert response.status_code == 200
            assert response.json()["val"] == 99
