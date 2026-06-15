"""Example 6: Lifecycle Hooks.

Shows the execution order with print statements.
"""

import uvicorn

from canary_framework import (
    before_shutdown,
    before_startup,
    module,
    service,
)
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@service()
class Database(ServiceBase):
    """Service with lifecycle hooks for connection management."""

    async def setup_connection(self):
        self.pool = "pool-ready"

    async def seed_data(self):
        self.data = {"users": [], "posts": []}

    @before_startup
    async def warm_cache(self):
        print("[Database] before_startup: cache warmed")

    @before_shutdown
    async def close_connections(self):
        print("[Database] before_shutdown: connections closed")
        self.pool = None


@service()
class Api(ServiceBase):
    router = Router(prefix="/api")

    async def load_routes(self):
        print("[Api] after_init: routes configured")

    @router.get("/status")
    async def status(self) -> dict:
        return {"status": "running"}


@module(services=[Database, Api])
class App(ModuleBase):
    pass


if __name__ == "__main__":
    print("=== Creating app ===")
    app = App()
    print("\n=== Calling init() ===")
    app.init()
    uvicorn.run(app, lifespan="on")
