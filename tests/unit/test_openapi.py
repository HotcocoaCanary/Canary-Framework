"""Unit tests for engine.openapi module."""

from typing import Any, cast

import pytest

from canary_framework.common import RouteInfo
from canary_framework.engine.openapi import generate_openapi_schema


@pytest.mark.unit
class TestGenerateOpenAPISchema:
    """Tests for generate_openapi_schema function."""

    def _make_route_info(self, **kwargs: object) -> RouteInfo:
        async def _dummy() -> None:
            pass

        defaults: dict[str, object] = {
            "handler": _dummy,
            "method": "GET",
            "path": "/",
            "starlette_path": "/",
            "path_params": [],
            "query_params": [],
            "param_meta": {},
        }
        defaults.update(kwargs)
        return RouteInfo(**defaults)  # type: ignore[arg-type]

    def test_empty_route_infos(self) -> None:
        """Test with empty route infos."""
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
        route_info = self._make_route_info(
            method="GET",
            path="/test",
            summary="Test endpoint",
            starlette_path="/test",
            router_prefix="/api",
            router_tags=["test"],
        )
        schema = generate_openapi_schema([route_info])
        paths = cast(dict[str, Any], schema["paths"])
        assert "/api/test" in paths
        assert "get" in paths["/api/test"]
