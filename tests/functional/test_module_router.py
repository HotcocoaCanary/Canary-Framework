"""Functional tests for Modules that have their own Router."""

import pytest
from httpx import ASGITransport, AsyncClient

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestModuleRouter:
    """Tests for Modules with their own Router."""

    @pytest.mark.asyncio
    async def test_module_with_router_no_children(self) -> None:
        """Scenario 6: Module with Router, no children — own routes work."""

        @module(services=[])
        class AppModule(ModuleBase):
            router = Router()

            @router.get("/status")
            async def status(self) -> dict[str, str]:
                return {"status": "ok"}

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/status")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            response = await client.get("/openapi.json")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_module_with_router_and_child_service(self) -> None:
        """Scenario 7: Module with Router + child Service — combined routes work."""

        @service()
        class ChildService(ServiceBase):
            router = Router()

            @router.get("/child")
            async def child(self) -> dict[str, str]:
                return {"from": "child"}

        @module(services=[ChildService])
        class AppModule(ModuleBase):
            router = Router()

            @router.get("/root")
            async def root(self) -> dict[str, str]:
                return {"from": "root"}

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.get("/root")
            assert r1.status_code == 200
            assert r1.json() == {"from": "root"}

            r2 = await client.get("/child")
            assert r2.status_code == 200
            assert r2.json() == {"from": "child"}

            schema = (await client.get("/openapi.json")).json()
            assert "/root" in schema["paths"]
            assert "/child" in schema["paths"]

    @pytest.mark.asyncio
    async def test_module_with_router_and_nested_module(self) -> None:
        """Scenario 8: Module with Router + nested Module with Service."""

        @service()
        class DeepService(ServiceBase):
            router = Router()

            @router.get("/deep")
            async def deep(self) -> dict[str, str]:
                return {"level": "deep"}

        @module(services=[DeepService])
        class SubModule(ModuleBase):
            pass

        @module(services=[SubModule])
        class RootModule(ModuleBase):
            router = Router()

            @router.get("/root")
            async def root(self) -> dict[str, str]:
                return {"from": "root"}

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.get("/root")
            assert r1.status_code == 200

            r2 = await client.get("/deep")
            assert r2.status_code == 200

            schema = (await client.get("/openapi.json")).json()
            assert "/root" in schema["paths"]
            assert "/deep" in schema["paths"]

    @pytest.mark.asyncio
    async def test_nested_module_each_with_router(self) -> None:
        """Both root and nested module have routers."""

        @service()
        class LeafService(ServiceBase):
            router = Router()

            @router.get("/leaf")
            async def leaf(self) -> dict[str, str]:
                return {"from": "leaf"}

        @module(services=[LeafService])
        class SubModule(ModuleBase):
            router = Router()

            @router.get("/sub-status")
            async def sub_status(self) -> dict[str, str]:
                return {"from": "sub-module"}

        @module(services=[SubModule])
        class RootModule(ModuleBase):
            router = Router()

            @router.get("/root-status")
            async def root_status(self) -> dict[str, str]:
                return {"from": "root-module"}

        app = RootModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/root-status")).status_code == 200
            assert (await client.get("/sub-status")).status_code == 200
            assert (await client.get("/leaf")).status_code == 200

            # All routes in one OpenAPI
            schema = (await client.get("/openapi.json")).json()
            assert len(schema["paths"]) == 3

    @pytest.mark.asyncio
    async def test_module_router_with_di(self) -> None:
        """Module's own router handler can use DI-injected dependencies."""

        @service()
        class ConfigProvider(ServiceBase):
            def get_mode(self) -> str:
                return "production"

        @module(services=[ConfigProvider])
        class AppModule(ModuleBase):
            router = Router()
            config_provider: ConfigProvider  # DI

            @router.get("/mode")
            async def mode(self) -> dict[str, str]:
                return {"mode": self.config_provider.get_mode()}

        app = AppModule()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/mode")
            assert response.status_code == 200
            assert response.json() == {"mode": "production"}
