"""Unit tests for the web route decorators."""

from __future__ import annotations

import pytest

from canary_framework.common.markers import ROUTE_ATTR
from canary_framework.web import delete, get, patch, post, put, route

pytestmark = pytest.mark.unit


def test_get_sets_route_marker() -> None:
    @get("/books")
    def handler() -> None: ...

    assert getattr(handler, ROUTE_ATTR) == ("GET", "/books")


def test_method_is_upper_cased() -> None:
    @route("get", "/x")
    def handler() -> None: ...

    assert getattr(handler, ROUTE_ATTR) == ("GET", "/x")


def test_path_gets_leading_slash() -> None:
    @post("books")
    def handler() -> None: ...

    assert getattr(handler, ROUTE_ATTR) == ("POST", "/books")


def test_all_verbs() -> None:
    for deco, verb in [
        (get, "GET"),
        (post, "POST"),
        (put, "PUT"),
        (patch, "PATCH"),
        (delete, "DELETE"),
    ]:

        @deco("/x")
        def handler() -> None: ...

        assert getattr(handler, ROUTE_ATTR) == (verb, "/x")
