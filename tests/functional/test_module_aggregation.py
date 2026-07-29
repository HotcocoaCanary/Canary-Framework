"""Functional tests for recursive module route aggregation."""

from __future__ import annotations

import pytest
from pydantic import Field

from canary_framework import CanaryConfig, get, module, router
from canary_framework.common import RouteContext
from canary_framework.core import ModuleBase, RouterBase

pytestmark = pytest.mark.functional


async def test_nested_modules_aggregate_prefix_tags_security_and_handlers() -> None:
    @router(prefix="/users", tags=("Users",))
    class UserRouter(RouterBase):
        @get("")
        async def list_users(self) -> list[dict[str, str]]:
            return [{"name": "Ada"}]

    class AppConfig(CanaryConfig):
        openapi_security_schemes: dict[str, dict[str, object]] = Field(
            default_factory=lambda: {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        )

    @module(prefix="/v1", tags=("v1",), children=(UserRouter,))
    class UserModule(ModuleBase):
        return_marker = "users"

    @module(
        prefix="/api",
        security=("bearerAuth",),
        children=(UserModule,),
        config=AppConfig,
    )
    class App(ModuleBase):
        return_marker = "app"

    app = App()
    await app.init()
    routes = app._collect_routes(RouteContext())

    assert [(route.method, route.full_path) for route in routes] == [("GET", "/api/v1/users")]
    assert routes[0].tags == ("v1", "Users")
    assert routes[0].security == ("bearerAuth",)
    assert "bearerAuth" in app.config.openapi_security_schemes  # type: ignore[union-attr]
    child_module = app.direct_children[0]
    child_router = child_module.direct_children[0]
    assert child_router._cf_dependency_engine is None  # type: ignore[attr-defined]
    assert await routes[0].handler() == [{"name": "Ada"}]


async def test_sibling_router_routes_remain_in_declaration_order() -> None:
    @router(prefix="/first")
    class First(RouterBase):
        @get("")
        async def first(self) -> dict[str, str]:
            return {"name": "first"}

    @router(prefix="/second")
    class Second(RouterBase):
        @get("")
        async def second(self) -> dict[str, str]:
            return {"name": "second"}

    @module(children=(Second, First))
    class App(ModuleBase):
        pass

    app = App()
    await app.init()

    assert [route.full_path for route in app._collect_routes(RouteContext())] == [
        "/second",
        "/first",
    ]
