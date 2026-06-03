"""Unit tests for engine.openapi module."""

import json
from typing import Any, cast

import pytest

from canary_framework.common.markers import ROUTE_ATTR
from canary_framework.common.types import RouterMeta
from canary_framework.engine.openapi import (
    _parse_route_path,
    generate_openapi_schema,
    get_openapi_json,
)


@pytest.mark.unit
class TestParseRoutePath:
    """Tests for _parse_route_path function."""

    def test_parse_simple_path(self) -> None:
        """Test parse simple path with no params."""
        path, path_params, query_params = _parse_route_path("/simple")
        assert path == "/simple"
        assert path_params == []
        assert query_params == []

    def test_parse_path_with_params(self) -> None:
        """Test parse path with path params."""
        path, path_params, query_params = _parse_route_path("/items/{item_id}")
        assert path == "/items/{item_id}"
        assert path_params == ["item_id"]
        assert query_params == []

    def test_parse_with_query_params(self) -> None:
        """Test parse with query params."""
        path, path_params, query_params = _parse_route_path("/items?page={page}&limit={limit}")
        assert path == "/items"
        assert path_params == []
        assert query_params == ["page", "limit"]

    def test_parse_with_hash_params(self) -> None:
        """Test parse with hash params."""
        path, path_params, query_params = _parse_route_path("/items#section={section}")
        assert path == "/items"
        assert path_params == []
        assert query_params == ["section"]


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


@pytest.mark.unit
class TestGetOpenAPIJSON:
    """Tests for get_openapi_json function."""

    def test_returns_json_string(self) -> None:
        """Test returns JSON string."""
        json_str = get_openapi_json([])
        assert isinstance(json_str, str)
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "openapi" in parsed
