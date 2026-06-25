"""Functional tests for standalone Service scenarios."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import service
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestStandaloneService:
    """Tests for services started standalone (without a Module)."""

    @pytest.mark.asyncio
    async def test_service_without_router(self) -> None:
        """Scenario 1: Standalone service, no Router — starts, /docs → 404."""

        @service()
        class MyService(ServiceBase):
            pass

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # No routes defined, should 404
            response = await client.get("/docs")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_service_with_router(self) -> None:
        """Scenario 2: Standalone service with Router — routes work, docs available."""

        @service()
        class UserService(ServiceBase):
            router = Router(prefix="/api")

            @router.get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"message": "hello"}

            @router.get("/users/{user_id}")
            async def get_user(self, user_id: int) -> dict[str, object]:
                return {"id": user_id, "name": "Alice"}

        app = UserService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Route works
            response = await client.get("/api/hello")
            assert response.status_code == 200
            assert response.json() == {"message": "hello"}

            # Path param works
            response = await client.get("/api/users/42")
            assert response.status_code == 200
            assert response.json()["id"] == 42

            # OpenAPI docs available
            response = await client.get("/docs")
            assert response.status_code == 200

            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert schema["openapi"] == "3.0.3"
            assert "/api/hello" in schema["paths"]
            assert "/api/users/{user_id}" in schema["paths"]

    @pytest.mark.asyncio
    async def test_service_with_router_query_params(self) -> None:
        """Service with Router — query parameters work."""

        @service()
        class MathService(ServiceBase):
            router = Router()

            @router.get("/add?a={a}&b={b}")
            async def add(self, a: int, b: int) -> dict[str, int]:
                return {"result": a + b}

        app = MathService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/add?a=10&b=20")
            assert response.status_code == 200
            assert response.json() == {"result": 30}

    @pytest.mark.asyncio
    async def test_service_with_router_post_body(self) -> None:
        """Service with Router — POST with request body."""

        class Item(BaseModel):
            name: str
            price: float

        @service()
        class ShopService(ServiceBase):
            router = Router()

            @router.post("/items", response_model=Item)
            async def create(self, item: Item) -> Item:
                return item

        app = ShopService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/items", json={"name": "book", "price": 9.99})
            assert response.status_code == 200
            assert response.json()["name"] == "book"

    @pytest.mark.asyncio
    async def test_service_with_router_invalid_query(self) -> None:
        """Service with Router — invalid query param returns 400."""

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.get("/square?num={num}")
            async def square(self, num: int) -> dict[str, int]:
                return {"result": num * num}

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/square?num=abc")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_service_with_router_invalid_body(self) -> None:
        """Service with Router — invalid JSON body returns 400."""

        class Item(BaseModel):
            name: str

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.post("/items", request_model=Item)
            async def create(self, item: Item) -> Item:
                return item

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/items", content=b"not json", headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_service_with_router_validation_error(self) -> None:
        """Service with Router — Pydantic validation error returns 422."""

        class Item(BaseModel):
            name: str
            price: float

        @service()
        class MyService(ServiceBase):
            router = Router()

            @router.post("/items", request_model=Item)
            async def create(self, item: Item) -> Item:
                return item

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/items", json={"name": "book"})
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_service_multiple_routers_not_allowed(self) -> None:
        """A service can only have one Router attribute. Multiple routers is a design choice — second overwrites first routes at class definition time.
        This test verifies that the second router's routes work (they replace the first).
        """

        @service()
        class MyService(ServiceBase):
            router1 = Router(prefix="/v1")
            router = Router(prefix="/v2")  # redefines the `router` attribute

            @router.get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"version": "v2"}

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # v2 route works
            response = await client.get("/v2/hello")
            assert response.status_code == 200
            assert response.json() == {"version": "v2"}

    @pytest.mark.asyncio
    async def test_service_startup_without_routes_has_no_docs(self) -> None:
        """Standalone service with no routes generates no OpenAPI docs."""

        @service()
        class MyService(ServiceBase):
            pass

        app = MyService()
        app.init()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                response = await client.get(path)
                assert response.status_code == 404, f"{path} should 404"
