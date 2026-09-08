"""Unit tests for the web route decorators."""

from __future__ import annotations

import pytest

from canary_framework.common.markers import ROUTE_ATTR
from canary_framework.web import delete, get, patch, post, put, route

pytestmark = pytest.mark.unit


def test_get_sets_route_marker() -> None:
    @get("/books")
    async def handler() -> None: ...

    mark = getattr(handler, ROUTE_ATTR)
    assert (mark.method, mark.path) == ("GET", "/books")


def test_method_is_upper_cased() -> None:
    @route("get", "/x")
    async def handler() -> None: ...

    mark = getattr(handler, ROUTE_ATTR)
    assert (mark.method, mark.path) == ("GET", "/x")


def test_path_gets_leading_slash() -> None:
    @post("books")
    async def handler() -> None: ...

    mark = getattr(handler, ROUTE_ATTR)
    assert (mark.method, mark.path) == ("POST", "/books")


def test_all_verbs() -> None:
    for deco, verb in [
        (get, "GET"),
        (post, "POST"),
        (put, "PUT"),
        (patch, "PATCH"),
        (delete, "DELETE"),
    ]:

        @deco("/x")
        async def handler() -> None: ...

        mark = getattr(handler, ROUTE_ATTR)
        assert (mark.method, mark.path) == (verb, "/x")


def test_route_metadata_rides_along_on_the_marker() -> None:
    @post("/books", status_code=201, tags=["books"], summary="新建一本书", deprecated=True)
    async def handler() -> None: ...

    mark = getattr(handler, ROUTE_ATTR)
    assert mark.status_code == 201
    assert mark.tags == ("books",)
    assert mark.summary == "新建一本书"
    assert mark.deprecated is True


def test_metadata_defaults_are_inert() -> None:
    """不写元数据的路由，行为要和从前一模一样。"""

    @get("/x")
    async def handler() -> None: ...

    mark = getattr(handler, ROUTE_ATTR)
    assert (mark.status_code, mark.tags, mark.summary, mark.deprecated) == (200, (), None, False)
