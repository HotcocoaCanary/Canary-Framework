"""Integration tests for routing."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.integration
class TestRouting:
    """Integration tests for routing."""

    @pytest.mark.asyncio
    async def test_simple_get_route(self) -> None:
        """Test simple GET route."""

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"message": "Hello World"}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/MyRouter/hello")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello World"}

    @pytest.mark.asyncio
    async def test_route_with_path_params(self) -> None:
        """Test route with path params."""

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.get("/greet/{name}")
            async def greet(self, name: str) -> dict[str, str]:
                return {"message": f"Hello {name}"}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/MyRouter/greet/Alice")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello Alice"}

    @pytest.mark.asyncio
    async def test_route_with_query_params(self) -> None:
        """Test route with query params."""

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.get("/add")
            async def add(self, a: int, b: int) -> dict[str, int]:
                return {"result": a + b}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/MyRouter/add?a=2&b=3")
            assert response.status_code == 200
            assert response.json() == {"result": 5}

    @pytest.mark.asyncio
    async def test_post_route_with_body(self) -> None:
        """Test POST route with request body."""

        class User(BaseModel):
            name: str
            age: int

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.post("/users", request_model=User)
            async def create_user(self, user: User) -> dict[str, int | str]:
                return {"id": 1, "name": user.name, "age": user.age}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/MyRouter/users", json={"name": "Alice", "age": 30})
            assert response.status_code == 200
            assert response.json() == {"id": 1, "name": "Alice", "age": 30}

    @pytest.mark.asyncio
    async def test_router_with_prefix(self) -> None:
        """Test router with prefix."""

        @service()
        class MyRouter(ServiceBase):
            router = Router(prefix="/api/v1")

            @router.get("/test")
            async def test(self) -> dict[str, str]:
                return {"status": "ok"}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/test")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
