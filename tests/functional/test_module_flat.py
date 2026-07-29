"""Functional tests for flat compositional modules."""

import pytest

from canary_framework import CanaryConfig, get, module, router, service
from canary_framework.common import RouteContext
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

pytestmark = pytest.mark.functional


async def test_flat_module_wires_router_dependencies_and_collects_routes() -> None:
    @service()
    class Counter(ServiceBase):
        def __init__(self) -> None:
            super().__init__()
            self.value = 0

        def increment(self) -> int:
            self.value += 1
            return self.value

    @router(prefix="/api")
    class ApiRouter(RouterBase):
        counter: Counter

        @get("/count")
        async def count(self) -> dict[str, int]:
            return {"count": self.counter.increment()}

    @module(children=(ApiRouter,))
    class App(ModuleBase):
        pass

    app = App()
    await app.init()
    api = app.direct_children[0]
    routes = app._collect_routes(RouteContext())

    assert [route.full_path for route in routes] == ["/api/count"]
    assert await routes[0].handler() == {"count": 1}
    assert await routes[0].handler() == {"count": 2}
    assert api._cf_dependency_engine is None  # type: ignore[attr-defined]


async def test_flat_module_keeps_config_out_of_direct_children() -> None:
    class AppConfig(CanaryConfig):
        openapi_title: str = "Flat App"

    @service()
    class Worker(ServiceBase):
        pass

    @module(children=(Worker,), config=AppConfig)
    class App(ModuleBase):
        pass

    app = App()
    await app.init()

    assert tuple(type(child) for child in app.direct_children) == (Worker,)
    assert app.config is not None and app.config.openapi_title == "Flat App"


def test_config_class_cannot_be_declared_as_module_child() -> None:
    class AppConfig(CanaryConfig):
        pass

    with pytest.raises(TypeError, match="Config AppConfig cannot be a Module child"):

        @module(children=(AppConfig,))
        class Invalid(ModuleBase):
            pass
