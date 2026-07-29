"""Standalone RouterBase and route-context contract tests."""

from __future__ import annotations

import pytest

from canary_framework import get, module, router, service
from canary_framework.common import DependencyDirectionError, RouteContext
from canary_framework.core import ModuleBase, RouterBase, ServiceBase
from canary_framework.engine.routing import join_paths, ordered_unique


@service()
class Repository(ServiceBase):
    async def fetch(self, item_id: int) -> dict[str, int]:
        return {"item_id": item_id}


@router(prefix="/items", tags=("Items",), security=("bearerAuth",))
class ItemRouter(RouterBase):
    repository: Repository

    @get("/{item_id}")
    async def read(self, item_id: int) -> dict[str, int]:
        return await self.repository.fetch(item_id)


@pytest.mark.unit
async def test_standalone_router_recursively_injects_services() -> None:
    subject = ItemRouter()
    await subject.init()

    assert isinstance(subject.repository, Repository)
    routes = subject._collect_routes(RouteContext(prefix="/api", tags=("v1",)))
    assert len(routes) == 1
    assert routes[0].full_path == "/api/items/{item_id}"
    assert routes[0].tags == ("v1", "Items")
    assert routes[0].security == ("bearerAuth",)
    assert routes[0].handler.__self__ is subject


@pytest.mark.unit
def test_path_helpers_normalize_without_destroying_root() -> None:
    assert join_paths("/api/", "/items//{item_id}") == "/api/items/{item_id}"
    assert join_paths("", "/") == "/"
    assert join_paths("/api", "/search?q={query}") == "/api/search?q={query}"
    assert ordered_unique(("v1", "Items"), ("Items", "read")) == (
        "v1",
        "Items",
        "read",
    )


@pytest.mark.unit
async def test_router_without_dependencies_initializes() -> None:
    @router()
    class EmptyRouter(RouterBase):
        pass

    subject = EmptyRouter()
    await subject.init()
    assert subject.lifecycle_state.value == "initialized"
    assert subject.route_specs == ()


@pytest.mark.unit
async def test_router_dependency_direction_rejects_router_targets() -> None:
    @router()
    class OtherRouter(RouterBase):
        pass

    @router()
    class InvalidRouter(RouterBase):
        other: OtherRouter

    InvalidRouter.__annotations__["other"] = OtherRouter
    with pytest.raises(DependencyDirectionError, match="may depend only on Service"):
        await InvalidRouter().init()


@pytest.mark.unit
async def test_router_dependency_direction_rejects_module_targets() -> None:
    @module()
    class OtherModule(ModuleBase):
        pass

    @router()
    class InvalidRouter(RouterBase):
        other: OtherModule

    InvalidRouter.__annotations__["other"] = OtherModule
    with pytest.raises(DependencyDirectionError, match="may depend only on Service"):
        await InvalidRouter().init()
