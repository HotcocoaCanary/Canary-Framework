"""UserRouter — HTTP routes for user management."""

from __future__ import annotations

from typing import Any

from canary_framework.web.fastapi import delete, get, post, router
from user_module.service.user import UserService


@router(prefix="/api/users", deps=[UserService])
class UserRouter:
    """Route handler for user CRUD endpoints (prefix: /api/users)."""

    user_service: UserService

    @get("/")
    async def list_users(self) -> list[dict[str, str]]:
        """GET /api/users/ — list all users."""
        return self.user_service.list_users()

    @get("/{user_id}")
    async def get_user(self, user_id: str) -> dict[str, str | None]:
        """GET /api/users/{user_id} — get a single user."""
        user = self.user_service.get_user(user_id)
        if user is None:
            return {"detail": "not found"}
        return user

    @post("/")
    async def create_user(self, body: dict[str, Any]) -> dict[str, str]:
        """POST /api/users/ — create a new user."""
        return self.user_service.create_user(
            name=str(body.get("name", "unknown")),
            role=body.get("role"),
        )

    @delete("/{user_id}")
    async def delete_user(self, user_id: str) -> dict[str, str]:
        """DELETE /api/users/{user_id} — delete a user."""
        return {"id": user_id, "deleted": True}
