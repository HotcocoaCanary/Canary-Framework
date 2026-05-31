"""Unit tests for naming utilities."""

from __future__ import annotations

from canary_framework.engine import to_snake


class TestToSnake:
    def test_simple_pascal_case(self) -> None:
        assert to_snake("DBService") == "db_service"

    def test_multi_word(self) -> None:
        assert to_snake("DataSetAdminService") == "data_set_admin_service"

    def test_camel_case(self) -> None:
        assert to_snake("parseXML") == "parse_xml"

    def test_single_word(self) -> None:
        assert to_snake("Service") == "service"

    def test_empty_string(self) -> None:
        assert to_snake("") == ""
