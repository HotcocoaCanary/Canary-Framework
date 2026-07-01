"""Example 8: Path and Query Parameters.

Demonstrates: path parameters, query parameters,
type conversion (int, float, bool, str),
invalid/missing parameter → 422 responses.

布尔查询参数 / Boolean query params: ``true/True/1/yes/on`` → True,
``false/False/0/no/off`` → False（因此 ``?enabled=1`` 为 True）。
"""

import uvicorn

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


@service()
class CalcApi(ServiceBase):
    router = Router(prefix="/calc")

    # Path parameters
    @router.get("/square/{num}")
    async def square(self, num: int) -> dict:
        return {"result": num * num}

    @router.get("/divide/{a}/{b}")
    async def divide(self, a: float, b: float) -> dict:
        return {"result": a / b}

    # Query parameters — declared in the route path with ?key={key}
    @router.get("/search?q={query}&page={page}&limit={limit}")
    async def search(self, query: str = "", page: int = 1, limit: int = 10) -> dict:
        return {"query": query, "page": page, "limit": limit}

    # Boolean query parameters
    @router.get("/feature?enabled={flag}")
    async def feature(self, flag: bool) -> dict:
        return {"enabled": flag}

    # Mixed: path + query
    @router.get("/users/{user_id}/posts?tag={tag}")
    async def user_posts(self, user_id: int, tag: str = "") -> dict:
        return {"user_id": user_id, "tag": tag}


@module(services=[CalcApi])
class App(ModuleBase):
    pass


# Try these curl commands:
#   curl http://127.0.0.1:8000/calc/square/5
#   curl http://127.0.0.1:8000/calc/divide/10/3
#   curl "http://127.0.0.1:8000/calc/search?q=hello&page=2"
#   curl http://127.0.0.1:8000/calc/feature?enabled=true
#   curl http://127.0.0.1:8000/calc/feature?enabled=1   # → {"enabled": true}
#   curl http://127.0.0.1:8000/calc/users/42/posts?tag=python

if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
