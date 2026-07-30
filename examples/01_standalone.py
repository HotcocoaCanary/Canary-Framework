"""Example 1: Standalone Router.

A single router, started directly without a Module.
Demonstrates: explicit RouterBase, @router(), @get(), and standalone
await app.init() flow.
"""

from __future__ import annotations

import asyncio

import uvicorn

from canary_framework import get, router
from canary_framework.core import RouterBase


@router(prefix="/health")
class HealthRouter(RouterBase):
    """A standalone health router."""

    @get("")
    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


async def setup() -> RouterBase:
    app = HealthRouter()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
