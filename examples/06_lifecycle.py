"""Example 6: Lifecycle Hooks.

Shows the execution order with print statements.
"""

from __future__ import annotations

import asyncio

import uvicorn

from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase


@service()
class Database(ServiceBase):
    """Service with lifecycle phases for connection management."""

    async def on_init(self) -> None:
        self.pool: str | None = None
        self.data: dict[str, list[object]] = {"users": [], "posts": []}
        print("[Database] on_init: structural state prepared")

    async def on_startup(self) -> None:
        self.pool = "pool-ready"
        print("[Database] on_startup: pool ready")

    async def on_shutdown(self) -> None:
        print("[Database] on_shutdown: connections closed")
        self.pool = None


@router(prefix="/api")
class ApiRouter(RouterBase):
    async def on_init(self) -> None:
        print("[Api] on_init: routes ready")

    @get("/status")
    async def status(self) -> dict[str, str]:
        return {"status": "running"}


@module(children=(Database, ApiRouter))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    print("\n=== Calling init() ===")
    await app.init()
    return app


if __name__ == "__main__":
    print("=== Creating app ===")
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
