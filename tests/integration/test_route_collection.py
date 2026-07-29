"""Route resolution integration tests."""

from __future__ import annotations

import pytest

from canary_framework import get, router, service
from canary_framework.common import RouteContext
from canary_framework.core import RouterBase, ServiceBase

pytestmark = pytest.mark.integration


@service()
class Users(ServiceBase):
    async def fetch(self, uid: int) -> dict[str, int]:
        return {"uid": uid}


@router(prefix="/users", tags=("Users",))
class UserRouter(RouterBase):
    users: Users

    @get("/{uid}", tags=("Read",))
    async def read(self, uid: int) -> dict[str, int]:
        return await self.users.fetch(uid)

    @get("/search?q={query}")
    async def search(self, query: str) -> dict[str, str]:
        return {"query": query}


async def test_router_collects_resolved_routes_in_declaration_order() -> None:
    subject = UserRouter()
    await subject.init()

    routes = subject._collect_routes(RouteContext(prefix="/api", tags=("v1",)))
    assert [route.full_path for route in routes] == [
        "/api/users/{uid}",
        "/api/users/search?q={query}",
    ]
    assert [route.method for route in routes] == ["GET", "GET"]
    assert routes[0].tags == ("v1", "Users", "Read")
    assert routes[1].tags == ("v1", "Users")
    assert routes[0].handler.__self__ is subject


def test_route_specs_are_immutable_and_class_owned() -> None:
    assert isinstance(UserRouter.__cf_route_specs__, tuple)
    assert UserRouter().route_specs is UserRouter.__cf_route_specs__
