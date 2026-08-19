"""Integration tests — nested ``prefix`` mounting across ``@web_cocoa`` units."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from canary_framework import Canary, cocoa
from canary_framework.web import RouteRegistrationError, get, web_cocoa

pytestmark = pytest.mark.integration


def test_dependency_is_mounted_under_its_dependent_prefix() -> None:
    @web_cocoa(prefix="/admin")
    class AdminRouter:
        @get("/dashboard")
        async def dashboard(self) -> dict:
            return {"page": "dashboard"}

    @web_cocoa(prefix="/api", deps=[AdminRouter], title="Nested API", version="2.0.0")
    class ApiRouter:
        @get("/users")
        async def users(self) -> list[str]:
            return ["ada"]

    with TestClient(Canary(ApiRouter)) as client:
        assert client.get("/api/users").json() == ["ada"]
        assert client.get("/api/admin/dashboard").json() == {"page": "dashboard"}
        assert client.get("/admin/dashboard").status_code == 404  # 只在嵌套位置暴露

        doc = client.get("/openapi.json").json()
        assert set(doc["paths"]) == {"/api/users", "/api/admin/dashboard"}
        assert doc["info"] == {"title": "Nested API", "version": "2.0.0"}  # 取最外层


def test_non_web_unit_in_the_chain_does_not_break_nesting() -> None:
    @web_cocoa(prefix="/leaf")
    class Leaf:
        @get("/ping")
        async def ping(self) -> dict:
            return {"ok": True}

    @cocoa(deps=[Leaf])
    class Repo: ...

    @web_cocoa(prefix="/api", deps=[Repo])
    class Api:
        @get("/root")
        async def root(self) -> dict:
            return {"ok": True}

    with TestClient(Canary(Api)) as client:
        assert client.get("/api/leaf/ping").status_code == 200


def test_shared_unit_serves_one_instance_at_every_mount() -> None:
    @web_cocoa(prefix="/c")
    class C:
        def __init__(self) -> None:
            self.hits = 0

        @get("/hit")
        async def hit(self) -> dict:
            self.hits += 1
            return {"hits": self.hits, "id": id(self)}

    @web_cocoa(prefix="/b", deps=[C])
    class B: ...

    @web_cocoa(prefix="/a", deps=[B, C])
    class A: ...

    canary = Canary(A)
    with TestClient(canary) as client:
        first = client.get("/a/c/hit").json()
        second = client.get("/a/b/c/hit").json()

    # 两个挂载点，同一个实例：计数连续、id 相同
    assert (first["hits"], second["hits"]) == (1, 2)
    assert first["id"] == second["id"] == id(canary[C])


def test_prefix_applies_to_a_single_unit() -> None:
    @web_cocoa(prefix="/api/v1")
    class Api:
        @get("/ping")
        async def ping(self) -> dict:
            return {"ok": True}

    with TestClient(Canary(Api)) as client:
        assert client.get("/api/v1/ping").json() == {"ok": True}
        assert client.get("/ping").status_code == 404


async def test_colliding_mounted_paths_raise() -> None:
    @web_cocoa(prefix="/x")
    class Inner:
        @get("/y")
        async def y(self) -> None: ...

    @web_cocoa(deps=[Inner])
    class Outer:
        @get("/x/y")
        async def xy(self) -> None: ...

    canary = Canary(Outer)
    with pytest.raises(RouteRegistrationError) as excinfo:
        await canary.init()
        await canary.start()

    message = str(excinfo.value)
    assert "GET /x/y" in message
    assert "Outer" in message and "Inner" in message  # 冲突双方都点名
