"""Route aggregation integration tests for compositional modules."""

from __future__ import annotations

from typing import Any, cast

import pytest

from canary_framework import get, module, router, service
from canary_framework.common import RouteContext
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

pytestmark = pytest.mark.integration


@router(prefix="/users", tags=("Users",))
class UserRouter(RouterBase):
    @get("")
    async def list_users(self) -> list[dict[str, str]]:
        return [{"name": "Ada"}]


@service()
class OrdinaryService(ServiceBase):
    pass


@service()
class Dependency(ServiceBase):
    pass


@service()
class Consumer(ServiceBase):
    dependency: Dependency


@module(prefix="/v1", tags=("v1",), children=(UserRouter, OrdinaryService))
class UserModule(ModuleBase):
    pass


@module(prefix="/api", security=("bearerAuth",), children=(UserModule, Consumer))
class AppModule(ModuleBase):
    pass


async def test_nested_modules_fold_to_one_resolved_route_sequence() -> None:
    app = AppModule()
    await app.init()

    routes = app._collect_routes(RouteContext())

    assert [(route.method, route.full_path) for route in routes] == [("GET", "/api/v1/users")]
    assert routes[0].tags == ("v1", "Users")
    assert routes[0].security == ("bearerAuth",)


async def test_route_collection_preserves_declaration_order_not_topological_order() -> None:
    @router(prefix="/first")
    class FirstRouter(RouterBase):
        @get("")
        async def first(self) -> dict[str, str]:
            return {"route": "first"}

    @router(prefix="/second")
    class SecondRouter(RouterBase):
        @get("")
        async def second(self) -> dict[str, str]:
            return {"route": "second"}

    @module(children=(SecondRouter, Consumer, FirstRouter))
    class Ordered(ModuleBase):
        pass

    subject = Ordered()
    await subject.init()

    routes = subject._collect_routes(RouteContext())
    assert [route.full_path for route in routes] == ["/second", "/first"]
    assert tuple(type(child) for child in subject.direct_children) == (
        SecondRouter,
        Consumer,
        FirstRouter,
    )


async def test_router_collects_its_own_routes_with_inherited_context() -> None:
    subject = UserRouter()
    await subject.init()

    routes = subject._collect_routes(RouteContext(prefix="/api", tags=("v1",)))

    assert [route.full_path for route in routes] == ["/api/users"]
    assert routes[0].tags == ("v1", "Users")
    assert cast(Any, routes[0].handler).__self__ is subject
