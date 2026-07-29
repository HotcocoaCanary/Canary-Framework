"""Functional route-declaration edge cases for the redesigned router API."""

import pytest
from pydantic import BaseModel

from canary_framework import get, module, post, router, service
from canary_framework.common import RouteContext
from canary_framework.core import ModuleBase, RouterBase, ServiceBase
from canary_framework.engine.params import analyze_route
from canary_framework.engine.validation import validate_routes


class _NotDecorated:
    pass


class _SomeDep:
    pass


@pytest.mark.functional
class TestEdgeCases:
    """Tests for route and lifecycle boundaries before compiler integration."""

    @pytest.mark.asyncio
    async def test_undecorated_in_module_raises(self) -> None:
        @service()
        class ValidService(ServiceBase):
            pass

        with pytest.raises(TypeError, match="must be decorated"):

            @module(children=[ValidService, _NotDecorated])
            class _TestModule(ModuleBase):
                pass

    @pytest.mark.asyncio
    async def test_service_missing_di(self) -> None:
        @service()
        class ServiceWithDep(ServiceBase):
            missing_dep: _SomeDep

        app = ServiceWithDep()
        await app.init()
        assert getattr(app, "missing_dep", None) is None

    @pytest.mark.asyncio
    async def test_bool_query_param_annotation_is_resolved(self) -> None:
        @router()
        class MyRouter(RouterBase):
            @get("/check?flag={flag}")
            async def check(self, flag: bool) -> dict[str, bool]:
                return {"enabled": flag}

        app = MyRouter()
        await app.init()
        analysis = analyze_route(app._collect_routes(RouteContext())[0])
        assert analysis.query_params == ("flag",)
        assert analysis.parameters["flag"].annotation is bool
        assert not analysis.parameters["flag"].has_default

    @pytest.mark.asyncio
    async def test_service_root_path(self) -> None:
        @router()
        class RootRouter(RouterBase):
            @get("/")
            async def root(self) -> dict[str, str]:
                return {"home": "yes"}

        app = RootRouter()
        await app.init()
        routes = app._collect_routes(RouteContext())
        assert routes[0].full_path == "/"
        assert analyze_route(routes[0]).starlette_path == "/"

    @pytest.mark.asyncio
    async def test_multiple_methods_same_path(self) -> None:
        @router()
        class MyRouter(RouterBase):
            @get("/item")
            async def get_item(self) -> dict[str, str]:
                return {"method": "get"}

            @post("/item")
            async def post_item(self) -> dict[str, str]:
                return {"method": "post"}

        app = MyRouter()
        await app.init()
        routes = app._collect_routes(RouteContext())
        validated = validate_routes(routes, config=app.config)  # type: ignore[arg-type]
        assert [(item.route.method, item.analysis.starlette_path) for item in validated] == [
            ("GET", "/item"),
            ("POST", "/item"),
        ]

    @pytest.mark.asyncio
    async def test_router_prefix_trailing_slash(self) -> None:
        @router(prefix="/api/")
        class MyRouter(RouterBase):
            @get("/hello")
            async def hello(self) -> dict[str, str]:
                return {"ok": "yes"}

        app = MyRouter()
        await app.init()
        route = app._collect_routes(RouteContext())[0]
        assert route.full_path == "/api/hello"
        assert analyze_route(route).starlette_path == "/api/hello"

    @pytest.mark.asyncio
    async def test_router_prefix_sets_mount_path(self) -> None:
        @router(prefix="/custom")
        class MyRouter(RouterBase):
            @get("/test")
            async def test(self) -> dict[str, str]:
                return {"ok": "yes"}

        @module(children=[MyRouter])
        class AppModule(ModuleBase):
            pass

        app = AppModule()
        await app.init()
        assert app._collect_routes(RouteContext())[0].full_path == "/custom/test"

    @pytest.mark.asyncio
    async def test_deeply_nested_module(self) -> None:
        @router()
        class LeafRouter(RouterBase):
            @get("/data")
            async def data(self) -> dict[str, str]:
                return {"depth": "leaf"}

        @module(children=[LeafRouter])
        class Level3(ModuleBase):
            pass

        @module(children=[Level3])
        class Level2(ModuleBase):
            pass

        @module(children=[Level2])
        class Level1(ModuleBase):
            pass

        app = Level1()
        await app.init()
        routes = app._collect_routes(RouteContext())
        assert routes[0].full_path == "/data"
        assert (
            routes[0].handler.__self__
            is app.direct_children[0].direct_children[0].direct_children[0]
        )  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_return_model_metadata_is_preserved(self) -> None:
        class Item(BaseModel):
            name: str

        @router()
        class MyRouter(RouterBase):
            @get("/str")
            async def str_route(self) -> str:
                return "plain text"

            @get("/model", response_model=Item)
            async def model_route(self) -> Item:
                return Item(name="test")

        app = MyRouter()
        await app.init()
        routes = app._collect_routes(RouteContext())
        assert [route.full_path for route in routes] == ["/str", "/model"]
        assert routes[1].spec.response_model is Item
