"""Functional tests for OpenAPI docs."""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from canary_framework import get, post, router
from canary_framework.common.markers import get_router_meta
from canary_framework.engine.openapi import generate_openapi_schema


@pytest.mark.functional
class TestOpenAPIDocs:
    """Functional tests for OpenAPI docs."""

    def test_generate_openapi_schema(self) -> None:
        """Test generate OpenAPI schema."""

        class RequestItem(BaseModel):
            name: str
            value: int

        class ResponseItem(BaseModel):
            id: int
            name: str
            value: int

        @router()
        class MyRouter:
            @get("/items", summary="Get all items", tags=["items"])
            async def get_items(self) -> None:
                pass

            @post(
                "/items",
                summary="Create item",
                request_model=RequestItem,
                response_model=ResponseItem,
                tags=["items"],
            )
            async def create_item(self) -> None:
                pass

        router_meta = get_router_meta(MyRouter)
        assert router_meta is not None
        schema = generate_openapi_schema([router_meta])

        assert schema["openapi"] == "3.0.3"
        assert "info" in schema
        assert "paths" in schema
        components = cast(dict[str, Any], schema.get("components", {}))
        assert "schemas" in components

    def test_openapi_with_multiple_routers(self) -> None:
        """Test OpenAPI with multiple routers."""

        @router(tags=["users"])
        class UserRouter:
            @get("/users")
            async def get_users(self) -> None:
                pass

        @router(tags=["products"])
        class ProductRouter:
            @get("/products")
            async def get_products(self) -> None:
                pass

        user_meta = get_router_meta(UserRouter)
        product_meta = get_router_meta(ProductRouter)
        assert user_meta is not None
        assert product_meta is not None

        schema = generate_openapi_schema(
            [user_meta, product_meta],
            title="Shop API",
            version="1.0.0",
        )

        info = cast(dict[str, Any], schema["info"])
        assert info["title"] == "Shop API"
        assert info["version"] == "1.0.0"
        paths = cast(dict[str, Any], schema["paths"])
        path_keys = list(paths.keys())
        assert any("users" in path for path in path_keys)
        assert any("products" in path for path in path_keys)

    def test_openapi_with_descriptions(self) -> None:
        """Test OpenAPI with descriptions."""

        @router()
        class MyRouter:
            @get(
                "/test",
                summary="Test endpoint",
                description="This is a test endpoint that does nothing useful",
            )
            async def test(self) -> None:
                pass

        router_meta = get_router_meta(MyRouter)
        assert router_meta is not None
        schema = generate_openapi_schema([router_meta])

        paths = cast(dict[str, Any], schema["paths"])
        path_obj = cast(dict[str, Any], next(iter(paths.values())))
        assert "get" in path_obj
        get_obj = cast(dict[str, Any], path_obj["get"])
        assert get_obj["summary"] == "Test endpoint"
        assert "description" in get_obj
