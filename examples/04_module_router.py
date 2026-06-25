"""Example 4: Module with its own Router.

A Module that itself has routes, plus child services with routes.
Demonstrates: module-level Router, combined OpenAPI schema.
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
    router = Router()

    @router.get("/status")
    async def status(self) -> dict:
        return {"app": "running", "version": "0.5.0"}

    @router.get("/health")
    async def health(self) -> dict:
        return {"healthy": True}


if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
