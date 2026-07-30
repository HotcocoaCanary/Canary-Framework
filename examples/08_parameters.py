"""Example 8: Path and Query Parameters.

Demonstrates: path parameters, query parameters,
type conversion (int, float, bool, str),
invalid/missing parameter → 422 responses.

布尔查询参数 / Boolean query params: ``true/True/1/yes/on`` → True,
``false/False/0/no/off`` → False（因此 ``?enabled=1`` 为 True）。
"""

from __future__ import annotations

import asyncio

import uvicorn
from pydantic import Field

from canary_framework import get, module, router
from canary_framework.core import ModuleBase, RouterBase


@router(prefix="/calc")
class CalcRouter(RouterBase):
    # Path parameters
    @get("/square/{num}")
    async def square(self, num: int) -> dict[str, int]:
        return {"result": num * num}

    @get("/divide/{a}/{b}")
    async def divide(self, a: float, b: float) -> dict[str, float]:
        return {"result": a / b}

    # Query parameters — declared in the route path with ?key={key}
    @get("/search?q={query}&page={page}&limit={limit}")
    async def search(
        self,
        query: str = Field(default="", description="Search query"),
        page: int = Field(default=1, ge=1),
        limit: int = Field(default=10, ge=1, le=100),
    ) -> dict[str, int | str]:
        return {"query": query, "page": page, "limit": limit}

    # Boolean query parameters
    @get("/feature?enabled={flag}")
    async def feature(self, flag: bool) -> dict[str, bool]:
        return {"enabled": flag}

    # Mixed: path + query
    @get("/users/{user_id}/posts?tag={tag}")
    async def user_posts(self, user_id: int, tag: str | None = None) -> dict[str, int | str | None]:
        return {"user_id": user_id, "tag": tag or ""}


@module(children=(CalcRouter,))
class App(ModuleBase):
    pass


# Try these curl commands:
#   curl http://127.0.0.1:8000/calc/square/5
#   curl http://127.0.0.1:8000/calc/divide/10/3
#   curl "http://127.0.0.1:8000/calc/search?q=hello&page=2"
#   curl http://127.0.0.1:8000/calc/feature?enabled=true
#   curl http://127.0.0.1:8000/calc/feature?enabled=1   # → {"enabled": true}
#   curl http://127.0.0.1:8000/calc/users/42/posts?tag=python


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
