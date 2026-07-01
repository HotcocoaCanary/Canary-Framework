"""Unit tests for decorators.router module."""

import pytest

from canary_framework import service
from canary_framework.common import get_service_meta
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@pytest.mark.unit
class TestRouterDecorator:
    """Tests for @service decorator with Router."""

    def test_router_decorator_marks_class(self) -> None:
        """Test @service marks class as service."""

        @service()
        class MyRouter(ServiceBase):
            pass

        meta_ = get_service_meta(MyRouter)
        assert meta_ is not None
        assert meta_.name

    def test_router_decorator_inherits_router_base(self) -> None:
        """Test @service makes class inherit from ServiceBase."""

        @service()
        class MyRouter(ServiceBase):
            pass

        assert issubclass(MyRouter, ServiceBase)

    def test_router_decorator_sets_meta(self) -> None:
        """Test @service sets metadata."""

        @service()
        class MyRouter(ServiceBase):
            pass

        meta = get_service_meta(MyRouter)
        assert meta is not None
        assert meta.name == "MyRouter"

    def test_router_decorator_with_prefix(self) -> None:
        """Test Router with prefix."""

        @service()
        class MyRouter(ServiceBase):
            router = Router(prefix="/api")

        assert isinstance(MyRouter.router, Router)
        assert MyRouter.router.prefix == "/api"

    def test_router_decorator_with_tags(self) -> None:
        """Test Router with tags."""

        @service()
        class MyRouter(ServiceBase):
            router = Router(tags=["api", "v1"])

        assert isinstance(MyRouter.router, Router)
        assert MyRouter.router.tags == ["api", "v1"]

    def test_router_decorator_collects_routes(self) -> None:
        """Test Router collects routes."""

        @service()
        class MyRouter(ServiceBase):
            router = Router()

            @router.get("/test")
            async def test_route(self) -> None:
                pass

        assert len(MyRouter.router._route_infos) == 1


@pytest.mark.unit
class TestHTTPMethodDecorators:
    """Tests for Router HTTP method decorators."""

    def test_get_decorator(self) -> None:
        """Test router.get decorator."""

        def my_route() -> None:
            pass

        r = Router()
        decorated = r.get("/test")(my_route)
        assert decorated is my_route
        assert len(r._route_infos) == 1
        assert r._route_infos[0].method == "GET"
        assert r._route_infos[0].path == "/test"

    def test_post_decorator(self) -> None:
        """Test router.post decorator."""

        def my_route() -> None:
            pass

        r = Router()
        decorated = r.post("/test")(my_route)
        assert decorated is my_route
        assert len(r._route_infos) == 1
        assert r._route_infos[0].method == "POST"
        assert r._route_infos[0].path == "/test"

    def test_put_decorator(self) -> None:
        """Test router.put decorator."""

        def my_route() -> None:
            pass

        r = Router()
        decorated = r.put("/test")(my_route)
        assert decorated is my_route
        assert len(r._route_infos) == 1
        assert r._route_infos[0].method == "PUT"
        assert r._route_infos[0].path == "/test"

    def test_delete_decorator(self) -> None:
        """Test router.delete decorator."""

        def my_route() -> None:
            pass

        r = Router()
        decorated = r.delete("/test")(my_route)
        assert decorated is my_route
        assert len(r._route_infos) == 1
        assert r._route_infos[0].method == "DELETE"
        assert r._route_infos[0].path == "/test"

    def test_patch_decorator(self) -> None:
        """Test router.patch decorator."""

        def my_route() -> None:
            pass

        r = Router()
        decorated = r.patch("/test")(my_route)
        assert decorated is my_route
        assert len(r._route_infos) == 1
        assert r._route_infos[0].method == "PATCH"
        assert r._route_infos[0].path == "/test"

    def test_route_with_extra_info(self) -> None:
        """Test route with extra info."""

        def my_route() -> None:
            pass

        r = Router()
        decorated = r.get(
            "/test",
            summary="Test summary",
            description="Test description",
            tags=["test"],
            deprecated=True,
            operation_id="testOperation",
        )(my_route)

        assert decorated is my_route
        route_info = r._route_infos[0]
        assert route_info.summary == "Test summary"
        assert route_info.description == "Test description"
        assert route_info.tags == ["test"]
        assert route_info.deprecated is True
        assert route_info.operation_id == "testOperation"

    @pytest.mark.unit
    def test_router_captures_body_param_name(self) -> None:
        """Test router captures body parameter name."""
        from pydantic import BaseModel

        from canary_framework.core.router import Router

        class Payload(BaseModel):
            name: str

        router = Router(prefix="/api")

        @router.put("/users/{user_id}")
        async def update(self: object, user_id: int, body: Payload) -> dict[str, object]:
            return {}

        (info,) = router._route_infos
        assert info.body_param == "body"
        assert info.request_model is Payload
