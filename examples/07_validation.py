"""Example 7: Request/Response Validation with Pydantic.

Demonstrates: Pydantic models for request/response, Field constraints,
auto-detection of request_model from type annotations,
ValidationError → 422 responses.
"""

import uvicorn
from pydantic import BaseModel, Field

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


# ── Pydantic models ──────────────────────────────────────
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


# ── Service ──────────────────────────────────────────────
@service()
class UserApi(ServiceBase):
    router = Router(prefix="/api")
    _users: list[dict] = []
    _next_id: int = 1

    @router.get("/users", response_model=list[UserResponse])
    async def list_users(self) -> list[dict]:
        return self._users

    @router.post("/users", response_model=UserResponse)
    async def create_user(self, user: CreateUser) -> dict:
        """request_model auto-detected from CreateUser type annotation."""
        new_user = {"id": self._next_id, **user.model_dump()}
        self._users.append(new_user)
        self._next_id += 1
        return new_user

    @router.get("/users/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> dict | tuple:
        for u in self._users:
            if u["id"] == user_id:
                return u
        return {"error": "Not found"}, 404


@module(services=[UserApi])
class App(ModuleBase):
    pass


if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
