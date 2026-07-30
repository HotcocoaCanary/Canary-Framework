"""Example 7: Request/Response Validation with Pydantic.

Demonstrates: Pydantic models for request/response, Field constraints,
auto-detection of request_model from type annotations,
ValidationError → 422 responses,
``(body, status)`` 元组返回可显式设置状态码（如 ``return {...}, 404``）。
A ``(body, status)`` tuple return sets the HTTP status (e.g. ``return {...}, 404``).
"""

from __future__ import annotations

import asyncio

import uvicorn
from pydantic import BaseModel, Field

from canary_framework import get, module, post, router
from canary_framework.core import ModuleBase, RouterBase


class CreateUser(BaseModel):
    """Request model with validation constraints."""

    name: str = Field(min_length=2, max_length=50, description="User name")
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$", description="Email")
    age: int = Field(ge=0, le=150, description="Age")


class UserResponse(BaseModel):
    """Response model."""

    id: int
    name: str
    email: str
    age: int


@router(prefix="/api")
class UserRouter(RouterBase):
    _users: list[dict[str, object]]
    _next_id: int

    def __init__(self) -> None:
        super().__init__()
        self._users = []
        self._next_id = 1

    @get("/users", response_model=list[UserResponse])
    async def list_users(self) -> list[dict[str, object]]:
        return self._users

    @post("/users", response_model=UserResponse)
    async def create_user(self, user: CreateUser) -> dict[str, object]:
        """request_model auto-detected from CreateUser type annotation."""
        new_user = {"id": self._next_id, **user.model_dump()}
        self._users.append(new_user)
        self._next_id += 1
        return new_user

    @get("/users/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> dict[str, object] | tuple[dict[str, str], int]:
        for user in self._users:
            if user["id"] == user_id:
                return user
        return {"error": "Not found"}, 404


@module(children=(UserRouter,))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
