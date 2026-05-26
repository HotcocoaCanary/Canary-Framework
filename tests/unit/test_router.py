"""Tests for :mod:`canary_framework.web.fastapi.decorators.router`.

Covers:
    - @router creates RouterMeta on __cf_service_meta__
    - @router sets __cf_router__ = True
    - @router with auto-generated name (to_snake)
    - @router with explicit name, deps, tags
    - @get / @post / @put / @delete / @patch with explicit params
    - Route decorator kwargs filtering (None excluded)
    - get_route_info extracts correct (method, path, kwargs)
    - is_router / is_route_method detection helpers
    - get_router_meta returns RouterMeta or default
"""

from __future__ import annotations

import pytest

from canary_framework.common._types import RouterMeta
from canary_framework.core.decorators.service import is_cf_service
from canary_framework.web.fastapi.decorators.router import (
    delete,
    get,
    get_route_info,
    get_router_meta,
    is_route_method,
    is_router,
    patch,
    post,
    put,
    router,
)

# ---------------------------------------------------------------------------
# @router decorator
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRouterDecorator:
    """Verify @router decorator behaviour."""

    def test_creates_router_meta(self) -> None:
        @router(prefix="/api")
        class MyRouter:
            pass

        assert is_router(MyRouter) is True
        assert is_cf_service(MyRouter) is True

        meta = get_router_meta(MyRouter)
        assert isinstance(meta, RouterMeta)
        assert meta.prefix == "/api"
        assert meta.tags == []
        assert meta.name == "my_router"

    def test_explicit_name(self) -> None:
        @router(prefix="/x", name="custom-name")
        class R:
            pass

        meta = get_router_meta(R)
        assert meta.name == "custom-name"

    def test_with_tags(self) -> None:
        @router(prefix="/api", tags=["users", "public"], name="tagged")
        class R:
            pass

        meta = get_router_meta(R)
        assert meta.tags == ["users", "public"]

    def test_with_deps(self) -> None:
        @router(prefix="/api", name="dep-router", deps=[str])
        class R:
            pass

        meta = get_router_meta(R)
        assert meta.deps == [str]

    def test_service_meta_is_router_meta(self) -> None:
        @router(prefix="/x", name="srv")
        class R:
            pass

        from canary_framework.core.decorators.service import get_service_meta

        meta = get_service_meta(R)
        assert isinstance(meta, RouterMeta)
        assert meta.prefix == "/x"

    def test_router_inherits_service_fields(self) -> None:
        @router(prefix="/api", name="srv", deps=[int])
        class R:
            pass

        meta = get_router_meta(R)
        assert meta.name == "srv"
        assert meta.deps == [int]

    def test_get_router_meta_on_non_router_returns_default(self) -> None:
        class Plain:
            pass

        meta = get_router_meta(Plain)
        assert isinstance(meta, RouterMeta)
        assert meta.name == ""


# ---------------------------------------------------------------------------
# is_router / is_route_method helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRouterDetection:
    """Verify introspectors correctly identify router classes and methods."""

    def test_is_router_true_for_router_class(self) -> None:
        @router(prefix="/", name="r")
        class R:
            pass

        assert is_router(R) is True

    def test_is_router_false_for_plain_class(self) -> None:
        class Plain:
            pass

        assert is_router(Plain) is False

    def test_is_route_method_true(self) -> None:
        @router(prefix="/", name="r")
        class R:
            @get("/path")
            def handler(self) -> None:
                pass

        assert is_route_method(R.handler) is True

    def test_is_route_method_false_for_plain_method(self) -> None:
        def plain() -> None:
            pass

        assert is_route_method(plain) is False


# ---------------------------------------------------------------------------
# @get / @post / @put / @delete / @patch
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRouteMethodDecorators:
    """Verify HTTP method decorators store correct metadata."""

    def test_get_with_path_only(self) -> None:
        @get("/items")
        def handler() -> None:
            pass

        method, path, kwargs = get_route_info(handler)
        assert method == "GET"
        assert path == "/items"
        assert kwargs == {}

    def test_post_with_status_code(self) -> None:
        @post("/items", status_code=201)
        def handler() -> None:
            pass

        _, path, kwargs = get_route_info(handler)
        assert path == "/items"
        assert kwargs == {"status_code": 201}

    def test_get_with_response_model(self) -> None:
        class User:
            pass

        @get("/users", response_model=User)
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs["response_model"] is User

    def test_get_with_tags(self) -> None:
        @get("/data", tags=["public"])
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs["tags"] == ["public"]

    def test_get_with_summary_and_description(self) -> None:
        @get("/data", summary="Get stuff", description="Detailed docs")
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs["summary"] == "Get stuff"
        assert kwargs["description"] == "Detailed docs"

    def test_get_with_dependencies(self) -> None:
        dep1 = object()

        @get("/secure", dependencies=[dep1])
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs["dependencies"] == [dep1]

    def test_get_with_deprecated(self) -> None:
        @get("/old", deprecated=True)
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs["deprecated"] is True

    def test_get_with_response_description(self) -> None:
        @get("/data", response_description="The response")
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs["response_description"] == "The response"

    def test_all_http_methods(self) -> None:
        @get("/a")
        def a() -> None: ...

        @post("/b")
        def b() -> None: ...

        @put("/c")
        def c() -> None: ...

        @delete("/d")
        def d() -> None: ...

        @patch("/e")
        def e() -> None: ...

        assert get_route_info(a)[0] == "GET"
        assert get_route_info(b)[0] == "POST"
        assert get_route_info(c)[0] == "PUT"
        assert get_route_info(d)[0] == "DELETE"
        assert get_route_info(e)[0] == "PATCH"

    def test_none_values_are_excluded_from_kwargs(self) -> None:
        @get("/path")
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert "status_code" not in kwargs
        assert "response_model" not in kwargs
        assert "summary" not in kwargs

    def test_partial_params(self) -> None:
        @get("/p", status_code=200)
        def handler() -> None:
            pass

        _, _, kwargs = get_route_info(handler)
        assert kwargs == {"status_code": 200}
        assert "response_model" not in kwargs

    def test_is_route_method_after_decorator(self) -> None:
        @get("/items")
        def handler() -> None:
            pass

        assert is_route_method(handler) is True

    def test_default_values_for_get_route_info(self) -> None:
        def plain() -> None:
            pass

        method, path, kwargs = get_route_info(plain)
        assert method == "GET"
        assert path == "/"
        assert kwargs == {}
