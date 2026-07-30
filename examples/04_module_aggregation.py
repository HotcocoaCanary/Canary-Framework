"""Example 4: Module Route Aggregation.

A Module that aggregates multiple routers without owning business routes.
Demonstrates: router children, explicit prefixes, and combined OpenAPI schema.

设计说明 / Design note:
    Canary 使用「显式前缀」模型 —— 路由挂在其 Router 的 ``prefix`` 下，
    没有按类名自动加 ``/{ServiceName}`` 命名空间。所以给每个 Router 一个
    明确的 ``prefix=`` 才能得到可预期、互不冲突的路径。
    Canary uses an explicit-prefix model: routes are served under their
    Router's ``prefix`` with NO automatic ``/{ServiceName}`` namespacing.
    Give each Router an explicit ``prefix=`` for predictable, collision-free paths.
"""

from __future__ import annotations

import asyncio

import uvicorn

from canary_framework import get, module, post, router
from canary_framework.core import ModuleBase, RouterBase


@router(prefix="/app")
class AppRouter(RouterBase):
    @get("/status")
    async def status(self) -> dict[str, str]:
        return {"app": "running", "version": "0.5.0"}

    @get("/health")
    async def health(self) -> dict[str, bool]:
        return {"healthy": True}


@router(prefix="/items")
class ItemRouter(RouterBase):
    items: dict[int, str]

    def __init__(self) -> None:
        super().__init__()
        self.items = {}

    @get("/list")
    async def list_items(self) -> dict[str, list[dict[str, int | str]]]:
        return {"items": [{"id": key, "name": value} for key, value in self.items.items()]}

    @post("/add?name={name}")
    async def add_item(self, name: str) -> dict[str, int | str]:
        new_id = len(self.items) + 1
        self.items[new_id] = name
        return {"id": new_id, "name": name}


@module(children=(AppRouter, ItemRouter))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


# Try these curl commands / 试试这些 curl 命令:
#   curl http://127.0.0.1:8000/app/status
#   curl http://127.0.0.1:8000/app/health
#   curl http://127.0.0.1:8000/items/list
#   curl -X POST "http://127.0.0.1:8000/items/add?name=widget"

if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
