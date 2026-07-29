"""Unit tests for compositional ModuleBase."""

import pytest
from pydantic import Field

from canary_framework import CanaryConfig, ServiceNotFoundError, get, module, router, service
from canary_framework.common import LifecycleState, RouteContext
from canary_framework.core import ModuleBase, RouterBase, ServiceBase


@pytest.mark.unit
async def test_empty_decorated_module_is_a_route_less_object() -> None:
    @module()
    class EmptyModule(ModuleBase):
        pass

    subject = EmptyModule()
    await subject.init()

    assert subject.direct_children == ()
    assert subject._collect_routes(RouteContext()) == ()
    assert subject.config is not None


@pytest.mark.unit
async def test_root_module_wires_typed_child_dependencies() -> None:
    @service()
    class Worker(ServiceBase):
        pass

    @module(children=(Worker,))
    class App(ModuleBase):
        worker: Worker

    app = App()
    await app.init()

    assert app.worker is app.direct_children[0]


@pytest.mark.unit
async def test_module_wiring_failure_rolls_back_initialized_children_once() -> None:
    events: list[str] = []

    @service()
    class Child(ServiceBase):
        async def _init(self) -> None:
            events.append("child-init")

        async def on_shutdown(self) -> None:
            events.append("child-on-shutdown")

    @service()
    class Missing(ServiceBase):
        pass

    @module(children=(Child,))
    class App(ModuleBase):
        missing: Missing

    app = App()

    with pytest.raises(ServiceNotFoundError, match="'Missing' is not registered"):
        await app.init()

    assert events == ["child-init", "child-on-shutdown"]
    assert app.lifecycle_state is LifecycleState.FAILED


@pytest.mark.unit
async def test_module_delegates_child_lifecycle_in_dependency_order() -> None:
    events: list[str] = []

    @service()
    class Dependency(ServiceBase):
        async def _init(self) -> None:
            events.append("dependency-init")

        async def _startup(self) -> None:
            events.append("dependency-startup")

        async def _shutdown(self) -> None:
            events.append("dependency-shutdown")

    @service()
    class Consumer(ServiceBase):
        dependency: Dependency

        async def _init(self) -> None:
            events.append("consumer-init")

        async def _startup(self) -> None:
            events.append("consumer-startup")

        async def _shutdown(self) -> None:
            events.append("consumer-shutdown")

    @module(children=(Consumer,))
    class App(ModuleBase):
        pass

    app = App()
    await app.init()
    await app.startup()
    await app.shutdown()

    assert events == [
        "dependency-init",
        "consumer-init",
        "dependency-startup",
        "consumer-startup",
        "consumer-shutdown",
        "dependency-shutdown",
    ]


@pytest.mark.unit
async def test_nested_module_routes_extend_context_and_inherit_config() -> None:
    class AppConfig(CanaryConfig):
        openapi_security_schemes: dict[str, dict[str, object]] = Field(
            default_factory=lambda: {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        )

    @router(prefix="/users", tags=("Users",))
    class UserRouter(RouterBase):
        @get("")
        async def list_users(self) -> list[dict[str, str]]:
            return [{"name": "Ada"}]

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
    child_router = child_module.direct_children[0]  # type: ignore[union-attr]
    assert child_router._cf_dependency_engine is None  # type: ignore[attr-defined]


@pytest.mark.unit
async def test_nested_module_uses_its_own_config_override() -> None:
    class RootConfig(CanaryConfig):
        openapi_title: str = "root"

    class ChildConfig(CanaryConfig):
        openapi_title: str = "child"

    @module(config=ChildConfig)
    class Child(ModuleBase):
        pass

    @module(children=(Child,), config=RootConfig)
    class Root(ModuleBase):
        pass

    root = Root()
    await root.init()

    child = root.direct_children[0]
    assert root.config is not None and root.config.openapi_title == "root"
    assert child.config is not None and child.config.openapi_title == "child"


@pytest.mark.unit
async def test_module_ignores_ordinary_services_during_route_collection() -> None:
    @service()
    class Ordinary(ServiceBase):
        pass

    @router()
    class Router(RouterBase):
        @get("/health")
        async def health(self) -> dict[str, str]:
            return {"status": "ok"}

    @module(children=(Ordinary, Router))
    class App(ModuleBase):
        pass

    app = App()
    await app.init()

    assert [route.full_path for route in app._collect_routes(RouteContext())] == ["/health"]
    assert tuple(type(child) for child in app.direct_children) == (Ordinary, Router)
