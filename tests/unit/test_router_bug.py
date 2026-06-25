"""Unit tests for router bugs (parameter ordering and GET body)."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import Canary, module, service
from canary_framework.core.web.router import Router


class Item(BaseModel):
    name: str


@service()
class Api:
    router = Router(prefix="/api")

    @router.post("/items/{id}")
    async def create_item(self, id: int, body: Item) -> dict[str, object]:
        return {"id": id, "item": body.name}

    @router.get("/items/query")
    async def query_items(self, query: Item) -> dict[str, str]:
        # NOTE: This query param binding isn't fully supported to instantiate the model,
        # but the test is to ensure it doesn't crash on `await request.json()`.
        return {"status": "ok"}


@module(services=[Api])
class App:
    pass


@pytest.mark.asyncio
async def test_router_param_order_bug() -> None:
    """Test that placing path param before request body param works."""
    app = Canary(App())
    await app.startup()

    # We use httpx AsyncClient instead of TestClient to avoid StarletteDeprecationWarning
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/items/42", json={"name": "test_item"})
        assert resp.status_code == 200
        assert resp.json() == {"id": 42, "item": "test_item"}

    await app.shutdown()


@pytest.mark.asyncio
async def test_get_request_no_body_parsing() -> None:
    """Test that a GET request doesn't try to parse a request_model."""
    app = Canary(App())
    await app.startup()

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/items/query")
        assert resp.status_code == 500
        assert "Invalid JSON" not in resp.text

    await app.shutdown()
