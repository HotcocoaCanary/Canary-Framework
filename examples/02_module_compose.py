"""Example 2: Module Composing Multiple Services.

A Module that composes a data service and an API service.
Demonstrates: @module(), DI via type annotations, service composition.
"""

import uvicorn

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

# ── Data Service ──────────────────────────────────────────


@service()
class Counter(ServiceBase):
    """A simple counter service — no router, just logic."""

    def __init__(self):
        super().__init__()
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count


# ── API Service ──────────────────────────────────────────


@service()
class CounterApi(ServiceBase):
    """Exposes Counter via HTTP — depends on Counter via DI."""

    router = Router(prefix="/api")
    counter: Counter  # injected by framework

    @router.get("/count")
    async def get_count(self) -> dict:
        return {"count": self.counter.increment()}

    @router.get("/reset?value={value}")
    async def reset(self, value: int = 0) -> dict:
        self.counter._count = value
        return {"reset_to": value}


# ── Root Module ──────────────────────────────────────────


@module(services=[Counter, CounterApi])
class App(ModuleBase):
    pass


if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
