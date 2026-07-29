"""Single-point assembly through the new compile_assembly pipeline."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from starlette.testclient import TestClient

from canary_framework.common import CanaryConfig, RouteCompilationError, RouteContext
from canary_framework.core import ModuleBase, RouterBase
from canary_framework.decorators import get, module, router
from canary_framework.engine.assembly import Assembly, compile_assembly

pytestmark = pytest.mark.functional


@router(prefix="/hello")
class HelloRouter(RouterBase):
    """Minimal router used to exercise the compiled assembly path."""

    @get("/")
    async def hi(self) -> dict[str, str]:
        return {"msg": "hi"}


@module(children=[HelloRouter])
class App(ModuleBase):
    """Module wrapper used to ensure the same pipeline handles roots."""

    pass


def compiled_assembly(root: RouterBase | ModuleBase) -> Assembly:
    """Initialize one root and compile its resolved routes."""
    asyncio.run(root.init())
    return compile_assembly(root._collect_routes(RouteContext()), config=CanaryConfig())


@pytest.mark.parametrize("root", [HelloRouter, App])
def test_compiled_assembly_serves_business_routes_and_docs(
    root: type[RouterBase | ModuleBase],
) -> None:
    assembly = compiled_assembly(root())

    paths = cast("dict[str, object]", assembly.openapi["paths"])
    assert "/hello" in paths

    with TestClient(assembly.asgi_app) as client:
        assert client.get("/hello").json() == {"msg": "hi"}
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200


def test_compiled_assembly_has_no_docs_when_no_routes_exist() -> None:
    assembly = compile_assembly((), config=CanaryConfig())

    assert assembly.routes == ()
    assert assembly.openapi == {}

    with TestClient(assembly.asgi_app) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404


def test_compiled_assembly_rejects_colliding_routes() -> None:
    @router()
    class A(RouterBase):
        @get("/x")
        async def a(self) -> dict[str, str]:
            return {}

    @router()
    class B(RouterBase):
        @get("/x")
        async def b(self) -> dict[str, str]:
            return {}

    @module(children=[A, B])
    class Bad(ModuleBase):
        pass

    with pytest.raises(RouteCompilationError, match="duplicate route GET /x"):
        compiled_assembly(Bad())
