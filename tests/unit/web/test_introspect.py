"""Unit tests for the web introspection helpers."""

from __future__ import annotations

import inspect
from typing import Annotated

import pytest
from pydantic import BaseModel
from starlette.requests import Request

from canary_framework.web import get
from canary_framework.web.decorator.introspect import routes_of
from canary_framework.web.decorator.params import Query
from canary_framework.web.decorator.resolve import location_of, path_param_names, resolve_meta
from canary_framework.web.infra.naming import header_name

pytestmark = pytest.mark.unit


def test_path_param_names_ignores_converter() -> None:
    assert path_param_names("/books/{book_id}/x/{id:int}") == {"book_id", "id"}


def test_header_name_converts_underscore() -> None:
    assert header_name("x_token") == "x-token"


def test_routes_of_scans_mro_base_first() -> None:
    class Mixin:
        @get("/mixin")
        def mixin_route(self) -> None: ...

    class Service(Mixin):
        @get("/own")
        def own_route(self) -> None: ...

    routes = routes_of(Service())
    assert [path for (_method, path, _fn) in routes] == ["/mixin", "/own"]


def test_resolve_meta_annotated_style() -> None:
    type_, marker, default = resolve_meta(
        Annotated[int, Query(default=10)], inspect.Parameter.empty
    )
    assert type_ is int
    assert isinstance(marker, Query)
    assert default == 10


def test_resolve_meta_classic_default_style() -> None:
    type_, marker, default = resolve_meta(int, Query(default=5))
    assert type_ is int
    assert isinstance(marker, Query)
    assert default == 5


def test_resolve_meta_required_when_no_default() -> None:
    _type, marker, default = resolve_meta(int, inspect.Parameter.empty)
    assert marker is None
    assert default is inspect.Parameter.empty


def test_location_of_pydantic_model_is_body() -> None:
    class M(BaseModel):
        x: int

    assert location_of(M, None, "m", set()) == "body"


def test_location_of_request_is_request() -> None:
    assert location_of(Request, None, "req", set()) == "request"


def test_location_of_path_param() -> None:
    assert location_of(int, None, "book_id", {"book_id"}) == "path"


def test_location_of_plain_scalar_is_query() -> None:
    assert location_of(int, None, "limit", set()) == "query"
