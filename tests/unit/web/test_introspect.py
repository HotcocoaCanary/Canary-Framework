"""Unit tests for the web introspection helpers."""

from __future__ import annotations

import warnings
from collections.abc import Awaitable
from typing import Annotated, cast

import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from starlette.requests import Request

from canary_framework.web import get
from canary_framework.web.decorator.introspect import routes_of
from canary_framework.web.decorator.params import Header
from canary_framework.web.decorator.resolve import location_of, path_param_names, unwrap
from canary_framework.web.infra.naming import header_name

pytestmark = pytest.mark.unit


def test_path_param_names_ignores_converter() -> None:
    assert path_param_names("/books/{book_id}/x/{id:int}") == {"book_id", "id"}


def test_header_name_converts_underscore() -> None:
    assert header_name("x_token") == "x-token"


def test_routes_of_scans_mro_base_first() -> None:
    class Mixin:
        @get("/mixin")
        async def mixin_route(self) -> None: ...

    class Service(Mixin):
        @get("/own")
        async def own_route(self) -> None: ...

    routes = [(m.method, m.path, fn) for m, fn in routes_of(Service())]
    assert [path for (_method, path, _fn) in routes] == ["/mixin", "/own"]


async def test_routes_of_keeps_same_named_mixin_routes() -> None:
    class KbMixin:
        @get("/kb/create")
        async def create(self) -> str:
            return "kb"

    class FileMixin:
        @get("/file/create")
        async def create(self) -> str:
            return "file"

    class CollMixin:
        @get("/coll/create")
        async def create(self) -> str:
            return "coll"

    class Router(KbMixin, FileMixin, CollMixin):
        pass

    routes = [(m.method, m.path, fn) for m, fn in routes_of(Router())]
    assert {(method, path) for method, path, _fn in routes} == {
        ("GET", "/kb/create"),
        ("GET", "/file/create"),
        ("GET", "/coll/create"),
    }
    # 绑定到具体 mixin 的方法：调用返回各自实现，而不是 MRO 里第一个同名方法。
    by_path = {path: fn for _method, path, fn in routes}
    assert await cast(Awaitable[str], by_path["/kb/create"]()) == "kb"
    assert await cast(Awaitable[str], by_path["/file/create"]()) == "file"
    assert await cast(Awaitable[str], by_path["/coll/create"]()) == "coll"


def test_routes_of_does_not_touch_pydantic_instance_attributes() -> None:
    class Model(BaseModel):
        x: int

    class API(Model):
        @get("/ping")
        async def ping(self) -> dict:
            return {"x": 1}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        routes_of(API(x=1))

    assert [w for w in caught if "Pydantic" in w.category.__name__] == []


def test_unwrap_splits_the_annotated_marker() -> None:
    bare, marker, validated = unwrap(Annotated[str, Header(alias="x-token")])
    assert bare is str
    assert isinstance(marker, Header)
    assert marker.alias == "x-token"
    assert validated is str  # 标记是我们的，不能漏给 pydantic


def test_unwrap_passes_a_bare_annotation_through() -> None:
    bare, marker, validated = unwrap(int)
    assert (bare, marker, validated) == (int, None, int)


def test_unwrap_keeps_the_constraints_pydantic_needs() -> None:
    """从前直接返回 args[0]，Field(gt=0) 这类约束被无声丢掉——既不校验也不进文档。"""
    bare, marker, validated = unwrap(Annotated[int, Header(), Field(gt=0)])
    assert bare is int  # 推断来源只看类型本身
    assert isinstance(marker, Header)
    # FieldInfo 之间不做值相等，直接看它还校不校验——那才是这条规则的意义。
    with pytest.raises(ValidationError):
        TypeAdapter(validated).validate_python(-1)


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
