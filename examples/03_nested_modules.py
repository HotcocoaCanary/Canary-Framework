"""Example 3: Nested Module Hierarchy.

Module → SubModule → Leaf Service.
Demonstrates: nested modules, DI across module boundaries, route propagation.
"""

import uvicorn

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

# ── Shared dependency ────────────────────────────────────


@service()
class SharedDB(ServiceBase):
    """A database service shared across the whole app."""

    def query(self, table: str) -> list[str]:
        return [f"row-{i}" for i in range(3)]


# ── User sub-module ──────────────────────────────────────


@service()
class UserService(ServiceBase):
    router = Router(prefix="/users")
    db: SharedDB  # DI — depends on root-level service

    @router.get("/list")
    async def list_users(self) -> dict:
        return {"users": self.db.query("users")}


@module(services=[UserService])
class UserModule(ModuleBase):
    """Sub-module for user-related functionality."""

    pass


# ── Order sub-module ─────────────────────────────────────


@service()
class OrderService(ServiceBase):
    router = Router(prefix="/orders")
    db: SharedDB

    @router.get("/list")
    async def list_orders(self) -> dict:
        return {"orders": self.db.query("orders")}


@module(services=[OrderService])
class OrderModule(ModuleBase):
    pass


# ── Root module ──────────────────────────────────────────


@module(services=[SharedDB, UserModule, OrderModule])
class App(ModuleBase):
    pass



if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
