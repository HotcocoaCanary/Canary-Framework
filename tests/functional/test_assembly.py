"""Single-point assembly: standalone == mounted, docs present, collision."""

from typing import cast

import pytest
from starlette.testclient import TestClient

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

pytestmark = pytest.mark.functional


@service()
class Hello(ServiceBase):
    router = Router(prefix="/hello")

    @router.get("/")
    async def hi(self) -> dict[str, str]:
        return {"msg": "hi"}


@module(services=[Hello])
class App(ModuleBase):
    pass


def test_standalone_service_serves_and_has_docs() -> None:
    svc = Hello()
    svc.init()
    with TestClient(svc) as c:
        assert c.get("/hello/").json() == {"msg": "hi"}
        assert c.get("/openapi.json").status_code == 200


def test_module_serves_same_paths_as_standalone() -> None:
    app = App()
    app.init()
    with TestClient(app) as c:
        assert c.get("/hello/").json() == {"msg": "hi"}
        assert "/hello/" in c.get("/openapi.json").json()["paths"]


def test_openapi_method_returns_same_dict() -> None:
    app = App()
    app.init()
    assert "/hello/" in cast("dict[str, object]", app.openapi()["paths"])


def test_no_prefix_collision_raises() -> None:
    @service()
    class A(ServiceBase):
        router = Router()

        @router.get("/x")
        async def a(self) -> dict[str, str]:
            return {}

    @service()
    class B(ServiceBase):
        router = Router()

        @router.get("/x")
        async def b(self) -> dict[str, str]:
            return {}

    @module(services=[A, B])
    class Bad(ModuleBase):
        pass

    bad = Bad()
    bad.init()
    with pytest.raises(ValueError, match="collision"):
        _ = bad.asgi_app
