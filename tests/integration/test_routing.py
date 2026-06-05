"""Integration tests for routing."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import get, module, post, router
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase


@pytest.mark.integration
class TestRouting:
    """Integration tests for routing."""

    @pytest.mark.asyncio
    async def test_simple_get_route(self) -> None:
        """Test simple GET route."""

        @router()
        class MyRouter(RouterBase):
            @get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"message": "Hello World"}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/MyRouterRouter/hello")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello World"}

    @pytest.mark.asyncio
    async def test_route_with_path_params(self) -> None:
        """Test route with path params."""

        @router()
        class MyRouter(RouterBase):
            @get("/greet/{name}")
            async def greet(self, name: str) -> dict[str, str]:
                return {"message": f"Hello {name}"}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/MyRouterRouter/greet/Alice")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello Alice"}

    @pytest.mark.asyncio
    async def test_route_with_query_params(self) -> None:
        """Test route with query params."""

        @router()
        class MyRouter(RouterBase):
            @get("/add?a={a}&b={b}")
            async def add(self, a: int, b: int) -> dict[str, int]:
                return {"result": a + b}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/MyRouterRouter/add?a=2&b=3")
            assert response.status_code == 200
            assert response.json() == {"result": 5}

    @pytest.mark.asyncio
    async def test_post_route_with_body(self) -> None:
        """Test POST route with request body."""

        class User(BaseModel):
            name: str
            age: int

        @router()
        class MyRouter(RouterBase):
            @post("/users", request_model=User)
            async def create_user(self, user: User) -> dict[str, int | str]:
                return {"id": 1, "name": user.name, "age": user.age}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/MyRouterRouter/users", json={"name": "Alice", "age": 30})
            assert response.status_code == 200
            assert response.json() == {"id": 1, "name": "Alice", "age": 30}

    @pytest.mark.asyncio
    async def test_router_with_prefix(self) -> None:
        """Test router with prefix."""

        @router(prefix="/api/v1")
        class MyRouter(RouterBase):
            @get("/test")
            async def test(self) -> dict[str, str]:
                return {"status": "ok"}

        @module(services=[MyRouter])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/test")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
