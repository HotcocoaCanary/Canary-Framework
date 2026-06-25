"""Functional tests for OpenAPI docs."""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from canary_framework import service
from canary_framework.common import RouteDef
from canary_framework.core.params import EndpointMeta, resolve_endpoint_meta
from canary_framework.core.web.openapi import generate_openapi_schema
from canary_framework.core.web.router import Router


def _collect_route_defs_and_deps(cls: type) -> list[tuple[RouteDef, EndpointMeta]]:
    """从服务类中收集 RouteDef 和 EndpointMeta 对象。"""
    router = getattr(cls, "router", None)
    if isinstance(router, Router):
        result: list[tuple[RouteDef, EndpointMeta]] = []
        for rdef in router._route_defs:
            dep = resolve_endpoint_meta(
                path=rdef.path,
                call=rdef.handler,
                is_endpoint=True,
                request_model=rdef.request_model,
                http_method=rdef.method,
            )
            result.append((rdef, dep))
        return result
    return []


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

        @service()
        class MyRouter:
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

        route_defs_and_deps = _collect_route_defs_and_deps(MyRouter)
        assert len(route_defs_and_deps) == 2
        schema = generate_openapi_schema(route_defs_and_deps)

        assert schema["openapi"] == "3.0.3"
        assert "info" in schema
        assert "paths" in schema
        components = cast(dict[str, Any], schema.get("components", {}))
        assert "schemas" in components

    def test_openapi_with_multiple_routers(self) -> None:
        """Test OpenAPI with multiple routers."""

        @service()
        class UserRouter:
            router = Router()

            @router.get("/users")
            async def get_users(self) -> None:
                pass

        @service()
        class ProductRouter:
            router = Router()

            @router.get("/products")
            async def get_products(self) -> None:
                pass

        route_defs_and_deps = _collect_route_defs_and_deps(
            UserRouter
        ) + _collect_route_defs_and_deps(ProductRouter)
        schema = generate_openapi_schema(
            route_defs_and_deps,
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

        @service()
        class MyRouter:
            router = Router()

            @router.get(
                "/test",
                summary="Test endpoint",
                description="This is a test endpoint that does nothing useful",
            )
            async def test(self) -> None:
                pass

        route_defs_and_deps = _collect_route_defs_and_deps(MyRouter)
        schema = generate_openapi_schema(route_defs_and_deps)

        paths = cast(dict[str, Any], schema["paths"])
        path_obj = cast(dict[str, Any], next(iter(paths.values())))
        assert "get" in path_obj
        get_obj = cast(dict[str, Any], path_obj["get"])
        assert get_obj["summary"] == "Test endpoint"
        assert "description" in get_obj
