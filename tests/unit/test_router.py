"""Unit tests for core.router module."""

import pytest
from starlette.responses import JSONResponse, PlainTextResponse

from canary_framework.core.router import (
    _auto_response,
    _convert_param,
)
from canary_framework.core.router._utils import parse_route_path


@pytest.mark.unit
class TestParseRoutePath:
    """Tests for parse_route_path function."""

    def test_simple_path(self) -> None:
        """Test simple path with no params."""
        path, path_params, query_params = parse_route_path("/simple")
        assert path == "/simple"
        assert path_params == []
        assert query_params == []

    def test_path_with_path_params(self) -> None:
        """Test path with path params."""
        path, path_params, query_params = parse_route_path("/items/{item_id}")
        assert path == "/items/{item_id}"
        assert path_params == ["item_id"]
        assert query_params == []

    def test_path_with_query_params(self) -> None:
        """Test path with query params."""
        path, path_params, query_params = parse_route_path("/items?page={page}&limit={limit}")
        assert path == "/items"
        assert path_params == []
        assert query_params == ["page", "limit"]

    def test_path_with_path_and_query_params(self) -> None:
        """Test path with both path and query params."""
        path, path_params, query_params = parse_route_path(
            "/items/{item_id}?page={page}&limit={limit}"
        )
        assert path == "/items/{item_id}"
        assert path_params == ["item_id"]
        assert query_params == ["page", "limit"]


@pytest.mark.unit
class TestConvertParam:
    """Tests for _convert_param function."""

    def test_convert_to_int(self) -> None:
        """Test convert to int."""
        assert _convert_param("123", int) == 123

    def test_convert_to_float(self) -> None:
        """Test convert to float."""
        assert _convert_param("123.45", float) == 123.45

    def test_convert_to_bool(self) -> None:
        """Test convert to bool."""
        assert _convert_param("true", bool) is True
        assert _convert_param("false", bool) is False

    def test_no_conversion(self) -> None:
        """Test no conversion."""
        assert _convert_param("test", str) == "test"
        assert _convert_param("test", None) == "test"


@pytest.mark.unit
class TestAutoResponse:
    """Tests for _auto_response function."""

    def test_response_passthrough(self) -> None:
        """Test Response is passed through."""
        response = PlainTextResponse("test")
        result = _auto_response(response)
        assert result is response

    def test_dict_to_json(self) -> None:
        """Test dict becomes JSONResponse."""
        data = {"key": "value"}
        result = _auto_response(data)
        assert isinstance(result, JSONResponse)

    def test_list_to_json(self) -> None:
        """Test list becomes JSONResponse."""
        data = [1, 2, 3]
        result = _auto_response(data)
        assert isinstance(result, JSONResponse)

    def test_string_to_plaintext(self) -> None:
        """Test string becomes PlainTextResponse."""
        result = _auto_response("test")
        assert isinstance(result, PlainTextResponse)

    def test_other_to_plaintext(self) -> None:
        """Test other types become PlainTextResponse."""
        result = _auto_response(123)
        assert isinstance(result, PlainTextResponse)
