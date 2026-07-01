"""Route collection (perception + fold) tests."""

from types import MethodType
from typing import cast

import pytest

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

pytestmark = pytest.mark.integration


@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{uid}")
    async def get(self, uid: int) -> dict[str, int]:
        return {"uid": uid}


@service()
class Orders(ServiceBase):
    router = Router(prefix="/orders")

    @router.get("/")
    async def list(self) -> list[object]:
        return []


@module(services=[Users, Orders])
class App(ModuleBase):
    pass


def test_leaf_service_collects_with_prefix() -> None:
    u = Users()
    routes = u._cf_collect_routes()
    assert [r.full_path for r in routes] == ["/users/{uid}"]


def test_module_folds_children() -> None:
    app = App()
    app.init()
    paths = sorted(r.full_path for r in app._cf_collect_routes())
    assert paths == ["/orders/", "/users/{uid}"]


def test_collected_handler_is_bound() -> None:
    u = Users()
    (r,) = u._cf_collect_routes()
    # 绑定后无需再传 self / 可访问实例
    assert cast(MethodType, r.handler).__self__ is u
