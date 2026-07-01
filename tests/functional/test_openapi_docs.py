"""Functional tests for OpenAPI docs."""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from canary_framework import config, module, service
from canary_framework.common.config import CanaryConfig
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestOpenAPIDocs:
    """Functional tests for OpenAPI docs (end-to-end via ``app.openapi()``)."""

    def test_generate_openapi_schema(self) -> None:
        """Test generate OpenAPI schema."""

        class RequestItem(BaseModel):
            name: str
            value: int

        class ResponseItem(BaseModel):
            id: int
            name: str
            value: int

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.get("/items", summary="Get all items", tags=["items"])
            async def get_items(self) -> None:
                pass

            @router.post(
                "/items",
                summary="Create item",
                request_model=RequestItem,
                response_model=ResponseItem,
                tags=["items"],
            )
            async def create_item(self) -> None:
                pass

        app = MyRouter()
        app.init()
        schema = app.openapi()

        assert schema["openapi"] == "3.0.3"
        assert "info" in schema
        assert "paths" in schema
        components = cast(dict[str, Any], schema.get("components", {}))
        assert "schemas" in components
        # 两条路由（GET + POST /items）都应被收集 / both routes collected
        paths = cast(dict[str, Any], schema["paths"])
        assert "/items" in paths
        assert set(paths["/items"].keys()) == {"get", "post"}

    def test_openapi_with_multiple_routers(self) -> None:
        """Test OpenAPI with multiple routers."""

        @service()
        class UserRouter(ServiceBase):
            router = Router()

            @router.get("/users")
            async def get_users(self) -> None:
                pass

        @service()
        class ProductRouter(ServiceBase):
            router = Router()

            @router.get("/products")
            async def get_products(self) -> None:
                pass

        @config()
        class ShopConfig(CanaryConfig):
            openapi_title: str = "Shop API"
            openapi_version: str = "1.0.0"

        @module(config=ShopConfig, services=[UserRouter, ProductRouter])
        class ShopApp(ModuleBase):
            pass

        app = ShopApp()
        app.init()
        schema = app.openapi()

        info = cast(dict[str, Any], schema["info"])
        assert info["title"] == "Shop API"
        assert info["version"] == "1.0.0"
        paths = cast(dict[str, Any], schema["paths"])
        path_keys = list(paths.keys())
        assert any("users" in path for path in path_keys)
        assert any("products" in path for path in path_keys)

    def test_openapi_with_descriptions(self) -> None:
        """Test OpenAPI with descriptions."""

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.get(
                "/test",
                summary="Test endpoint",
                description="This is a test endpoint that does nothing useful",
            )
            async def test(self) -> None:
                pass

        app = MyRouter()
        app.init()
        schema = app.openapi()

        paths = cast(dict[str, Any], schema["paths"])
        path_obj = cast(dict[str, Any], next(iter(paths.values())))
        assert "get" in path_obj
        get_obj = cast(dict[str, Any], path_obj["get"])
        assert get_obj["summary"] == "Test endpoint"
        assert "description" in get_obj
