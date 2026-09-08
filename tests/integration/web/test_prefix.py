"""Integration tests — ``prefix`` is a unit's absolute mount path.

前缀是绝对的：一个 ``@web_cocoa`` 单元的路由挂在哪，只由它自己的 ``prefix`` 决定，
与它被谁依赖无关。依赖关系决定启动顺序，不决定 URL。
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from canary_framework import Canary
from canary_framework.web import RouteRegistrationError, get, web_cocoa

pytestmark = pytest.mark.integration


def test_prefix_applies_to_a_single_unit() -> None:
    @web_cocoa(prefix="/api/v1")
    class Api:
        @get("/ping")
        async def ping(self) -> dict:
            return {"ok": True}

    with TestClient(Canary(Api)) as client:
        assert client.get("/api/v1/ping").json() == {"ok": True}
        assert client.get("/ping").status_code == 404


def test_a_dependency_keeps_its_own_prefix() -> None:
    """被依赖不改变挂载点——想挂到 ``/api`` 之下就自己写全。"""

    @web_cocoa(prefix="/admin")
    class AdminRouter:
        @get("/dashboard")
        async def dashboard(self) -> dict:
            return {"page": "dashboard"}

    @web_cocoa(prefix="/api", deps=[AdminRouter], title="Two Routers", version="2.0.0")
    class ApiRouter:
        @get("/users")
        async def users(self) -> list[str]:
            return ["ada"]

    with TestClient(Canary(ApiRouter)) as client:
        assert client.get("/api/users").json() == ["ada"]
        assert client.get("/admin/dashboard").json() == {"page": "dashboard"}
        assert client.get("/api/admin/dashboard").status_code == 404

        doc = client.get("/openapi.json").json()
        assert set(doc["paths"]) == {"/api/users", "/admin/dashboard"}
        assert doc["info"] == {"title": "Two Routers", "version": "2.0.0"}  # 取最外层


def test_one_unit_one_mount_even_when_reached_twice() -> None:
    """被两条依赖路径引用，仍然只有一个实例、一个挂载点。"""

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
        first = client.get("/c/hit").json()
        second = client.get("/c/hit").json()
        assert client.get("/a/b/c/hit").status_code == 404

    assert (first["hits"], second["hits"]) == (1, 2)
    assert first["id"] == second["id"] == id(canary[C])


async def test_colliding_paths_raise() -> None:
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
