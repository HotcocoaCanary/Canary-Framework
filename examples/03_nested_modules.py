"""Example 3: Nested Module Hierarchy.

Module → SubModule → Leaf Service.
Demonstrates: nested modules, DI across module boundaries, route propagation.
"""

from __future__ import annotations

import asyncio

import uvicorn

from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase


@service()
class SharedDB(ServiceBase):
    """A database service shared across the whole app."""

    def query(self, table: str) -> list[str]:
        return [f"{table}-row-{index}" for index in range(3)]


@router(prefix="/records")
class RecordRouter(RouterBase):
    db: SharedDB

    @get("")
    async def records(self) -> dict[str, list[str]]:
        return {"records": self.db.query("records")}


@module(prefix="/v1", children=(RecordRouter,))
class Feature(ModuleBase):
    """Sub-module for record-related functionality."""


@module(prefix="/api", children=(Feature, SharedDB))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
