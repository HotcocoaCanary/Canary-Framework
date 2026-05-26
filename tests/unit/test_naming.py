"""Tests for :mod:`canary_framework.core.algorithms.naming`."""

from __future__ import annotations

import pytest

from canary_framework.core.algorithms.naming import to_snake


@pytest.mark.unit
class TestToSnake:
    """Unit tests for PascalCase → snake_case conversion."""

    def test_simple_two_words(self) -> None:
        assert to_snake("DBService") == "db_service"

    def test_compound_three_words(self) -> None:
        assert to_snake("DataSetAdminService") == "data_set_admin_service"

    def test_acronym_sequence(self) -> None:
        assert to_snake("HttpAPI") == "http_api"

    def test_uppercase_acronym_only(self) -> None:
        assert to_snake("HTTPS") == "https"

    def test_single_word(self) -> None:
        assert to_snake("Service") == "service"

    def test_already_snake_case(self) -> None:
        assert to_snake("db_service") == "db_service"

    def test_mixed_case_with_numbers(self) -> None:
        assert to_snake("Api2Gateway") == "api2_gateway"

    def test_all_lowercase(self) -> None:
        assert to_snake("dbservice") == "dbservice"

    def test_empty_string(self) -> None:
        assert to_snake("") == ""

    @pytest.mark.parametrize(
        "input_name, expected",
        [
            ("XMLParser", "xml_parser"),
            ("parseXML", "parse_xml"),
            ("IOStream", "io_stream"),
            ("MyHTTPSServer", "my_https_server"),
            ("ABC", "abc"),
        ],
    )
    def test_edge_cases(self, input_name: str, expected: str) -> None:
        assert to_snake(input_name) == expected
