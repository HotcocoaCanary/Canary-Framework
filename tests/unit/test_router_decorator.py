"""Unit tests for decorators.router module."""

import pytest

from canary_framework.common import ROUTE_ATTR, get_router_meta, is_cf_router
from canary_framework.core.router import RouterBase
from canary_framework.decorators.router import (
    delete,
    get,
    patch,
    post,
    put,
    router,
)


@pytest.mark.unit
class TestRouterDecorator:
    """Tests for @router decorator."""

    def test_router_decorator_marks_class(self) -> None:
        """Test @router marks class as router."""

        @router()
        class MyRouter(RouterBase):
            pass

        assert is_cf_router(MyRouter)

    def test_router_decorator_inherits_router_base(self) -> None:
        """Test @router makes class inherit from RouterBase."""

        @router()
        class MyRouter(RouterBase):
            pass

        assert issubclass(MyRouter, RouterBase)

    def test_router_decorator_sets_meta(self) -> None:
        """Test @router sets metadata."""

        @router()
        class MyRouter(RouterBase):
            pass

        meta = get_router_meta(MyRouter)
        assert meta is not None
        assert meta.name == "MyRouterRouter"
        assert meta.prefix == ""
        assert meta.tags == []
        assert meta.routes == []

    def test_router_decorator_with_prefix(self) -> None:
        """Test @router with prefix."""

        @router(prefix="/api")
        class MyRouter(RouterBase):
            pass

        meta = get_router_meta(MyRouter)
        assert meta is not None
        assert meta.prefix == "/api"

    def test_router_decorator_with_tags(self) -> None:
        """Test @router with tags."""

        @router(tags=["api", "v1"])
        class MyRouter(RouterBase):
            pass

        meta = get_router_meta(MyRouter)
        assert meta is not None
        assert meta.tags == ["api", "v1"]

    def test_router_decorator_collects_routes(self) -> None:
        """Test @router collects routes."""

        @router()
        class MyRouter(RouterBase):
            @get("/test")
            async def test_route(self) -> None:
                pass

        meta = get_router_meta(MyRouter)
        assert meta is not None
        assert len(meta.routes) == 1


@pytest.mark.unit
class TestHTTPMethodDecorators:
    """Tests for HTTP method decorators."""

    def test_get_decorator(self) -> None:
        """Test @get decorator."""

        def my_route() -> None:
            pass

        decorated = get("/test")(my_route)
        assert hasattr(decorated, ROUTE_ATTR)
        route_info = getattr(decorated, ROUTE_ATTR)
        assert route_info["method"] == "GET"
        assert route_info["path"] == "/test"

    def test_post_decorator(self) -> None:
        """Test @post decorator."""

        def my_route() -> None:
            pass

        decorated = post("/test")(my_route)
        assert hasattr(decorated, ROUTE_ATTR)
        route_info = getattr(decorated, ROUTE_ATTR)
        assert route_info["method"] == "POST"
        assert route_info["path"] == "/test"

    def test_put_decorator(self) -> None:
        """Test @put decorator."""

        def my_route() -> None:
            pass

        decorated = put("/test")(my_route)
        assert hasattr(decorated, ROUTE_ATTR)
        route_info = getattr(decorated, ROUTE_ATTR)
        assert route_info["method"] == "PUT"
        assert route_info["path"] == "/test"

    def test_delete_decorator(self) -> None:
        """Test @delete decorator."""

        def my_route() -> None:
            pass

        decorated = delete("/test")(my_route)
        assert hasattr(decorated, ROUTE_ATTR)
        route_info = getattr(decorated, ROUTE_ATTR)
        assert route_info["method"] == "DELETE"
        assert route_info["path"] == "/test"

    def test_patch_decorator(self) -> None:
        """Test @patch decorator."""

        def my_route() -> None:
            pass

        decorated = patch("/test")(my_route)
        assert hasattr(decorated, ROUTE_ATTR)
        route_info = getattr(decorated, ROUTE_ATTR)
        assert route_info["method"] == "PATCH"
        assert route_info["path"] == "/test"

    def test_route_with_extra_info(self) -> None:
        """Test route with extra info."""

        def my_route() -> None:
            pass

        decorated = get(
            "/test",
            summary="Test summary",
            description="Test description",
            tags=["test"],
            deprecated=True,
            operation_id="testOperation",
        )(my_route)

        route_info = getattr(decorated, ROUTE_ATTR)
        assert route_info["summary"] == "Test summary"
        assert route_info["description"] == "Test description"
        assert route_info["tags"] == ["test"]
        assert route_info["deprecated"] is True
        assert route_info["operation_id"] == "testOperation"
