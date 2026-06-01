"""OpenAPI Schema generation tests."""

import pytest
from pydantic import BaseModel, Field

from canary_framework.common import RouterMeta, ROUTE_ATTR
from canary_framework.engine.openapi import (
    generate_openapi_schema,
    get_openapi_json,
)


class UserModel(BaseModel):
    """A user model for testing."""

    id: int = Field(description="User ID")
    name: str = Field(description="User name")
    email: str = Field(description="User email")


class TestOpenAPISchema:
    """Test OpenAPI Schema generation."""

    def test_generate_empty_schema(self):
        """Test generating schema with no routers."""
        schema = generate_openapi_schema([])
        assert schema["openapi"] == "3.0.3"
        assert schema["info"]["title"] == "Canary Framework API"
        assert schema["paths"] == {}

    def test_generate_schema_with_custom_info(self):
        """Test generating schema with custom title and description."""
        schema = generate_openapi_schema(
            [],
            title="Test API",
            version="2.0.0",
            description="Test description",
        )
        assert schema["info"]["title"] == "Test API"
        assert schema["info"]["version"] == "2.0.0"
        assert schema["info"]["description"] == "Test description"

    def test_generate_schema_with_route(self):
        """Test generating schema with a single route."""

        def sample_route():
            pass

        setattr(
            sample_route,
            ROUTE_ATTR,
            {
                "method": "GET",
                "path": "/users",
                "summary": "Get users",
                "description": "Get all users",
                "tags": ["users"],
                "deprecated": False,
                "operation_id": "get_users",
                "response_model": None,
                "responses": {},
            },
        )

        router_meta = RouterMeta(
            name="api",
            prefix="/api",
            tags=["api"],
            routes=[sample_route],
        )

        schema = generate_openapi_schema([router_meta])

        assert "/api/users" in schema["paths"]
        assert "get" in schema["paths"]["/api/users"]
        assert schema["paths"]["/api/users"]["get"]["summary"] == "Get users"
        assert schema["paths"]["/api/users"]["get"]["description"] == "Get all users"
        assert set(schema["paths"]["/api/users"]["get"]["tags"]) == {"api", "users"}
        assert schema["paths"]["/api/users"]["get"]["operationId"] == "get_users"

    def test_generate_schema_with_response_model(self):
        """Test generating schema with a response model."""

        def sample_route():
            pass

        setattr(
            sample_route,
            ROUTE_ATTR,
            {
                "method": "GET",
                "path": "/users/{id}",
                "summary": "Get user",
                "response_model": UserModel,
                "responses": {},
            },
        )

        router_meta = RouterMeta(
            name="api",
            prefix="/api",
            routes=[sample_route],
        )

        schema = generate_openapi_schema([router_meta])

        assert "UserModel" in schema["components"]["schemas"]
        assert schema["paths"]["/api/users/{id}"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"] == "#/components/schemas/UserModel"

    def test_generate_schema_with_deprecated(self):
        """Test generating schema with deprecated route."""

        def sample_route():
            pass

        setattr(
            sample_route,
            ROUTE_ATTR,
            {
                "method": "GET",
                "path": "/old",
                "deprecated": True,
            },
        )

        router_meta = RouterMeta(
            name="api",
            routes=[sample_route],
        )

        schema = generate_openapi_schema([router_meta])

        assert schema["paths"]["/old"]["get"]["deprecated"] is True

    def test_get_openapi_json(self):
        """Test getting OpenAPI JSON string."""
        json_str = get_openapi_json([])
        assert isinstance(json_str, str)
        # Verify it's valid JSON
        import json

        data = json.loads(json_str)
        assert data["openapi"] == "3.0.3"

    def test_generate_schema_with_request_model(self):
        """Test generating schema with a request model."""

        def sample_route():
            pass

        setattr(
            sample_route,
            ROUTE_ATTR,
            {
                "method": "POST",
                "path": "/users",
                "summary": "Create user",
                "request_model": UserModel,
                "responses": {},
            },
        )

        router_meta = RouterMeta(
            name="api",
            prefix="/api",
            routes=[sample_route],
        )

        schema = generate_openapi_schema([router_meta])

        assert "UserModel" in schema["components"]["schemas"]
        assert schema["paths"]["/api/users"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]["$ref"] == "#/components/schemas/UserModel"

    def test_generate_schema_with_path_params(self):
        """Test generating schema with path parameters."""

        def sample_route():
            pass

        setattr(
            sample_route,
            ROUTE_ATTR,
            {
                "method": "GET",
                "path": "/users/{user_id}",
                "path_params": {
                    "user_id": {"type": "int", "description": "User ID", "required": True}
                },
            },
        )

        router_meta = RouterMeta(
            name="api",
            prefix="/api",
            routes=[sample_route],
        )

        schema = generate_openapi_schema([router_meta])

        params = schema["paths"]["/api/users/{user_id}"]["get"]["parameters"]
        assert len(params) == 1
        assert params[0]["name"] == "user_id"
        assert params[0]["in"] == "path"
        assert params[0]["required"] is True
        assert params[0]["schema"]["type"] == "integer"

    def test_generate_schema_with_query_params(self):
        """Test generating schema with query parameters."""

        def sample_route():
            pass

        setattr(
            sample_route,
            ROUTE_ATTR,
            {
                "method": "GET",
                "path": "/users",
                "query_params": {
                    "page": {"type": "int", "description": "Page number", "required": False},
                    "limit": {"type": "int", "description": "Items per page", "required": False},
                },
            },
        )

        router_meta = RouterMeta(
            name="api",
            prefix="/api",
            routes=[sample_route],
        )

        schema = generate_openapi_schema([router_meta])

        params = schema["paths"]["/api/users"]["get"]["parameters"]
        assert len(params) == 2
        param_names = [p["name"] for p in params]
        assert "page" in param_names
        assert "limit" in param_names