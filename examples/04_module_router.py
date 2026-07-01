"""Example 4: Module with its own Router.

A Module that itself has routes, plus child services with routes.
Demonstrates: module-level Router, explicit prefixes, combined OpenAPI schema.

设计说明 / Design note:
    Canary 使用「显式前缀」模型 —— 路由挂在其 Router 的 ``prefix`` 下，
    没有按类名自动加 ``/{ServiceName}`` 命名空间。所以给每个 Router 一个
    明确的 ``prefix=`` 才能得到可预期、互不冲突的路径。
    Canary uses an explicit-prefix model: routes are served under their
    Router's ``prefix`` with NO automatic ``/{ServiceName}`` namespacing.
    Give each Router an explicit ``prefix=`` for predictable, collision-free paths.
"""

import uvicorn

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

# ── Child service ────────────────────────────────────────


@service()
class ItemService(ServiceBase):
    router = Router(prefix="/items")
    items: dict[int, str] = {}

    @router.get("/list")
    async def list_items(self) -> dict:
        return {"items": [{"id": k, "name": v} for k, v in self.items.items()]}

    @router.post("/add?name={name}")
    async def add_item(self, name: str) -> dict:
        new_id = len(self.items) + 1
        self.items[new_id] = name
        return {"id": new_id, "name": name}


# ── Root Module with its own Router ──────────────────────


@module(services=[ItemService])
class App(ModuleBase):
    router = Router(prefix="/app")

    @router.get("/status")
    async def status(self) -> dict:
        return {"app": "running", "version": "0.5.0"}

    @router.get("/health")
    async def health(self) -> dict:
        return {"healthy": True}


# Try these curl commands / 试试这些 curl 命令:
#   curl http://127.0.0.1:8000/app/status
#   curl http://127.0.0.1:8000/app/health
#   curl http://127.0.0.1:8000/items/list
#   curl -X POST "http://127.0.0.1:8000/items/add?name=widget"

if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
