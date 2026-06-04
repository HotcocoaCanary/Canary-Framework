"""Unit tests for engine.openapi module."""

from typing import Any, cast

import pytest

from canary_framework.common import ROUTE_ATTR
from canary_framework.common.routing import parse_route_path
from canary_framework.common.types import RouterMeta
from canary_framework.engine.openapi import generate_openapi_schema


@pytest.mark.unit
class TestParseRoutePath:
    """Tests for parse_route_path function."""

    def test_parse_simple_path(self) -> None:
        """Test parse simple path with no params."""
        path, path_params, query_params = parse_route_path("/simple")
        assert path == "/simple"
        assert path_params == []
        assert query_params == []

    def test_parse_path_with_params(self) -> None:
        """Test parse path with path params."""
        path, path_params, query_params = parse_route_path("/items/{item_id}")
        assert path == "/items/{item_id}"
        assert path_params == ["item_id"]
        assert query_params == []

    def test_parse_with_query_params(self) -> None:
        """Test parse with query params."""
        path, path_params, query_params = parse_route_path("/items?page={page}&limit={limit}")
        assert path == "/items"
        assert path_params == []
        assert query_params == ["page", "limit"]

    def test_parse_with_path_and_query_params(self) -> None:
        """Test parse with both path and query params."""
        path, path_params, query_params = parse_route_path(
            "/items/{item_id}?page={page}&limit={limit}"
        )
        assert path == "/items/{item_id}"
        assert path_params == ["item_id"]
        assert query_params == ["page", "limit"]


@pytest.mark.unit
class TestGenerateOpenAPISchema:
    """Tests for generate_openapi_schema function."""

    def test_empty_router_metas(self) -> None:
        """Test with empty router metas."""
        schema = generate_openapi_schema([])
        assert schema["openapi"] == "3.0.3"
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema

    def test_with_custom_title_and_version(self) -> None:
        """Test with custom title and version."""
        schema = generate_openapi_schema([], title="My API", version="2.0.0")
        info = cast(dict[str, Any], schema["info"])
        assert info["title"] == "My API"
        assert info["version"] == "2.0.0"

    def test_with_description(self) -> None:
        """Test with description."""
        schema = generate_openapi_schema([], description="Test API")
        info = cast(dict[str, Any], schema["info"])
        assert info["description"] == "Test API"

    def test_with_routes(self) -> None:
        """Test with routes."""

        def sample_get() -> None:
            pass

        setattr(
            sample_get, ROUTE_ATTR, {"method": "GET", "path": "/test", "summary": "Test endpoint"}
        )

        router_meta = RouterMeta(
            name="test_router", prefix="/api", tags=["test"], routes=[sample_get]
        )

        schema = generate_openapi_schema([router_meta])
        paths = cast(dict[str, Any], schema["paths"])
        assert "/api/test" in paths
        assert "get" in paths["/api/test"]
