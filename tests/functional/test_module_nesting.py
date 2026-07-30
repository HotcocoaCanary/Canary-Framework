"""Functional tests for nested compositional modules."""

from typing import cast

import pytest

from canary_framework import CanaryConfig, get, module, router, service
from canary_framework.common import RouteContext
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

pytestmark = pytest.mark.functional


async def test_nested_module_inherits_nearest_config_and_parent_service() -> None:
    class RootConfig(CanaryConfig):
        openapi_title: str = "Root App"

    @service()
    class SharedDatabase(ServiceBase):
        def value(self) -> str:
            return "shared"

    @router(prefix="/records")
    class RecordRouter(RouterBase):
        database: SharedDatabase

        @get("")
        async def records(self) -> dict[str, str]:
            return {"source": self.database.value()}

    @module(prefix="/v1", children=(RecordRouter,))
    class Feature(ModuleBase):
        pass

    @module(children=(Feature, SharedDatabase), config=RootConfig)
    class Root(ModuleBase):
        pass

    root = Root()
    await root.init()
    feature = cast(ModuleBase, root.direct_children[0])
    shared = cast(SharedDatabase, root.direct_children[1])
    router_instance = cast(RecordRouter, feature.direct_children[0])
    route = root._collect_routes(RouteContext())[0]

    assert feature.config is root.config
    assert router_instance.config is root.config
    assert router_instance.database is shared
    assert await route.handler() == {"source": "shared"}


async def test_nested_module_own_config_becomes_nearest_for_descendants() -> None:
    class RootConfig(CanaryConfig):
        openapi_title: str = "Root"

    class FeatureConfig(CanaryConfig):
        openapi_title: str = "Feature"

    @service()
    class Worker(ServiceBase):
        pass

    @module(children=(Worker,), config=FeatureConfig)
    class Feature(ModuleBase):
        pass

    @module(children=(Feature,), config=RootConfig)
    class Root(ModuleBase):
        pass

    root = Root()
    await root.init()
    feature = cast(ModuleBase, root.direct_children[0])
    worker = feature.direct_children[0]

    assert root.config is not None and root.config.openapi_title == "Root"
    assert feature.config is not None and feature.config.openapi_title == "Feature"
    assert worker.config is feature.config


async def test_route_less_nested_module_remains_in_composition_tree() -> None:
    @module()
    class Empty(ModuleBase):
        pass

    @module(children=(Empty,), prefix="/api")
    class Root(ModuleBase):
        pass

    root = Root()
    await root.init()

    assert isinstance(root.direct_children[0], Empty)
    assert root._collect_routes(RouteContext()) == ()
