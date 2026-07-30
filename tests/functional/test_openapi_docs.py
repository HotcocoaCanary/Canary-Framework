"""Functional coverage for compiling collected routes into OpenAPI."""

from typing import Any, cast

import pytest
from pydantic import BaseModel, Field

from canary_framework.common import CanaryConfig, RouteContext
from canary_framework.core import ModuleBase, RouterBase
from canary_framework.decorators import get, module, post, router
from canary_framework.engine.openapi import OpenAPICompiler
from canary_framework.engine.validation import validate_routes


class RequestItem(BaseModel):
    """Create-item request body."""

    name: str
    value: int


class ResponseItem(BaseModel):
    """Create-item response body."""

    id: int
    name: str
    value: int


@pytest.mark.functional
def test_compile_collected_router_routes() -> None:
    """Compile GET and POST declarations collected from one real router."""

    @router(prefix="/api")
    class ItemRouter(RouterBase):
        @get("/items", summary="Get all items", tags=("items",))
        async def get_items(self) -> None:
            return None

        @post(
            "/items",
            summary="Create item",
            request_model=RequestItem,
            response_model=ResponseItem,
            status_code=201,
            tags=("items",),
        )
        async def create_item(self, body: RequestItem) -> None:
            del body

    config = CanaryConfig()
    routes = ItemRouter()._collect_routes(RouteContext())
    document = OpenAPICompiler().compile(validate_routes(routes, config), config=config)

    paths = cast("dict[str, Any]", document["paths"])
    assert tuple(paths) == ("/api/items",)
    assert tuple(paths["/api/items"]) == ("get", "post")
    assert paths["/api/items"]["post"]["responses"]["201"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ResponseItem"}


@pytest.mark.functional
async def test_root_config_exclusively_supplies_document_metadata_and_schemes() -> None:
    """Nested config does not leak OpenAPI metadata or scheme definitions."""

    class RootConfig(CanaryConfig):
        openapi_title: str = "Shop API"
        openapi_version: str = "3.0.0"
        openapi_security_schemes: dict[str, dict[str, object]] = Field(
            default_factory=lambda: cast(
                dict[str, dict[str, object]], {"rootAuth": {"type": "http", "scheme": "bearer"}}
            )
        )

    class FeatureConfig(CanaryConfig):
        openapi_title: str = "Feature API"
        openapi_security_schemes: dict[str, dict[str, object]] = Field(
            default_factory=lambda: cast(
                dict[str, dict[str, object]],
                {"featureAuth": {"type": "apiKey", "in": "header", "name": "X-Feature"}},
            )
        )

    @router(prefix="/users")
    class UserRouter(RouterBase):
        @get("")
        async def users(self) -> None:
            return None

    @router(prefix="/products")
    class ProductRouter(RouterBase):
        @get("")
        async def products(self) -> None:
            return None

    @module(children=(UserRouter,), config=FeatureConfig, prefix="/feature")
    class FeatureModule(ModuleBase):
        pass

    @module(
        children=(FeatureModule, ProductRouter),
        config=RootConfig,
        security=("rootAuth",),
    )
    class ShopApp(ModuleBase):
        pass

    app = ShopApp()
    await app.init()
    assert app.config is not None
    routes = app._collect_routes(RouteContext())
    validated = validate_routes(routes, app.config)
    document = OpenAPICompiler().compile(validated, config=app.config)

    assert document["info"] == {"title": "Shop API", "version": "3.0.0"}
    components = cast("dict[str, Any]", document["components"])
    assert tuple(components["securitySchemes"]) == ("rootAuth",)
    paths = cast("dict[str, Any]", document["paths"])
    assert tuple(paths) == ("/feature/users", "/products")
    for path_item in paths.values():
        route_operation = next(iter(path_item.values()))
        assert route_operation["security"] == [{"rootAuth": []}]


@pytest.mark.functional
def test_collected_route_descriptions_compile_without_reanalysis() -> None:
    """Compiler consumes metadata and the canonical validated analysis."""

    @router(prefix="/api", tags=("Diagnostics",))
    class DiagnosticRouter(RouterBase):
        @get(
            "/test",
            summary="Test endpoint",
            description="This is a test endpoint that does nothing useful",
            deprecated=True,
        )
        async def test(self) -> None:
            return None

    config = CanaryConfig()
    validated = validate_routes(
        DiagnosticRouter()._collect_routes(RouteContext()),
        config,
    )
    document = OpenAPICompiler().compile(validated, config=config)
    paths = cast("dict[str, Any]", document["paths"])
    operation = cast("dict[str, Any]", paths["/api/test"]["get"])

    assert operation["summary"] == "Test endpoint"
    assert operation["description"] == "This is a test endpoint that does nothing useful"
    assert operation["deprecated"] is True
    assert operation["tags"] == ["Diagnostics"]
