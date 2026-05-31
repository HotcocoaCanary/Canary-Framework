"""Unit tests for web routing decorators."""

from __future__ import annotations

from canary_framework.common import ROUTE_ATTR, RouterMeta, get_service_meta, is_cf_router
from canary_framework.core import RouterBase
from canary_framework.decorators import get, router


class TestHTTPMethodDecorators:
    def test_get_decorator(self) -> None:
        @get("/items")
        async def handler(self, request):  # type: ignore[no-untyped-def]
            pass

        info = getattr(handler, ROUTE_ATTR)
        assert info["method"] == "GET"
        assert info["path"] == "/items"


class TestRouterDecorator:
    def test_router_injects_router_base(self) -> None:
        @router(prefix="/api", name="api")
        class ApiRouter:
            pass

        assert issubclass(ApiRouter, RouterBase)

    def test_is_cf_router(self) -> None:
        @router(name="r")
        class R:
            pass

        assert is_cf_router(R) is True

        class Plain:
            pass

        assert is_cf_router(Plain) is False

    def test_router_meta(self) -> None:
        @router(prefix="/v1", name="v1", tags=["api"])
        class V1:
            pass

        meta = get_service_meta(V1)
        assert isinstance(meta, RouterMeta)
        assert meta.prefix == "/v1"
        assert meta.tags == ["api"]

    def test_router_collects_routes(self) -> None:
        @router(name="collector")
        class Collector:
            @get("/hello")
            async def hello(self, request):  # type: ignore[no-untyped-def]
                return {"msg": "hi"}

        meta = get_service_meta(Collector)
        assert isinstance(meta, RouterMeta)
        assert len(meta.routes) == 1


class TestRouterBase:
    async def test_asgi_app(self) -> None:
        @router(name="test")
        class TestRouter:
            @get("/ping")
            async def ping(self, request):  # type: ignore[no-untyped-def]
                return {"pong": True}

        inst = TestRouter()
        app = inst.asgi_app  # type: ignore[attr-defined]
        assert app is not None
