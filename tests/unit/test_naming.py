"""Unit tests for the naming utility — ``to_snake``."""

import pytest

from canary_framework.core.infra.naming import to_snake

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("UserService", "user_service"),
        ("userService", "user_service"),
        ("HTTPServer", "http_server"),
        ("DB", "db"),
        ("user_service", "user_service"),
        ("user", "user"),
        ("A", "a"),
    ],
)
def test_to_snake(name: str, expected: str) -> None:
    assert to_snake(name) == expected


def test_to_snake_empty_name_falls_back_to_lowercase() -> None:
    assert to_snake("") == ""
