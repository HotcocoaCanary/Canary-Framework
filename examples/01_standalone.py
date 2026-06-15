"""Example 1: Standalone Service with Router.

A single service, started directly without a Module.
Demonstrates: @service(), Router, @router.get(), @router.post(),
standalone init() + startup() flow.
"""

import uvicorn

from canary_framework import service
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@service()
class MathService(ServiceBase):
    """A standalone math service with a Router."""

    router = Router(prefix="/api")

    @router.get("/add?a={a}&b={b}")
    async def add(self, a: int, b: int) -> dict:
        return {"result": a + b}

    @router.get("/greet/{name}")
    async def greet(self, name: str) -> dict:
        return {"hello": name}

    @router.post("/echo")
    async def echo(self, body: dict) -> dict:
        return {"you sent": body}


if __name__ == "__main__":
    app = MathService()
    app.init()
    uvicorn.run(app, lifespan="on")
