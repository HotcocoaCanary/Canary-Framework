"""Example 2: Module Composing Multiple Services.

A Module that composes a data service and an API router.
Demonstrates: @module(children=...), DI via type annotations,
service composition, and transitive child registration.
"""

from __future__ import annotations

import asyncio

import uvicorn

from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase


@service()
class Counter(ServiceBase):
    """A simple counter service — no router, just logic."""

    def __init__(self) -> None:
        super().__init__()
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count


@router(prefix="/api")
class CounterRouter(RouterBase):
    """Exposes Counter via HTTP — depends on Counter via DI."""

    counter: Counter

    @get("/count")
    async def get_count(self) -> dict[str, int]:
        return {"count": self.counter.increment()}

    @get("/reset?value={value}")
    async def reset(self, value: int = 0) -> dict[str, int]:
        self.counter._count = value
        return {"reset_to": value}


@module(children=(CounterRouter,))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
