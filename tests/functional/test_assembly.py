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


def test_pre_init_access_does_not_permanently_cache_empty_assembly() -> None:
    """Accessing asgi_app/openapi() before init() must not permanently poison
    the memoized assembly — after init() runs, the routes must be present.

    在 init() 之前访问 asgi_app/openapi() 不应永久污染记忆化的组装结果——
    init() 之后，路由必须能正确出现。
    """
    app = App()

    # Pre-init access: registry is not wired yet, so this observes an empty
    # assembly (no children collected).
    pre_init_paths = app.openapi().get("paths", {})
    assert pre_init_paths == {}

    app.init()

    with TestClient(app) as c:
        assert c.get("/hello/").status_code == 200
        assert c.get("/hello/").json() == {"msg": "hi"}
        assert "/hello/" in c.get("/openapi.json").json()["paths"]


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


def test_trailing_slash_prefix_does_not_double_slash() -> None:
    """Router(prefix="/api/") + @router.get("/x") must not diverge into
    routing at /api//x while OpenAPI advertises /api/x.

    Router(prefix="/api/") + @router.get("/x") 不应导致路由挂在 /api//x
    而 OpenAPI 却公布 /api/x 的分裂现象。
    """

    @service()
    class Trailing(ServiceBase):
        router = Router(prefix="/api/")

        @router.get("/x")
        async def x(self) -> dict[str, str]:
            return {"msg": "x"}

    svc = Trailing()
    svc.init()
    with TestClient(svc) as c:
        assert c.get("/api/x").status_code == 200
        paths = c.get("/openapi.json").json()["paths"]
        assert "/api/x" in paths
        assert "/api//x" not in paths
