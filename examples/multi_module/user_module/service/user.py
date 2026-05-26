"""UserService — user CRUD, depends on AuthService."""

from __future__ import annotations

from canary_framework import Context, on_init, service
from user_module.config import UserModuleConfig
from user_module.service.auth import AuthService


@service(name="user", deps=[AuthService])
class UserService:
    """User management service — depends on AuthService for token handling."""

    auth_service: AuthService

    def __init__(self) -> None:
        self._users: dict[str, dict[str, str]] = {}

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(UserModuleConfig)
        self._users = {
            "1": {"name": "Alice", "role": "admin"},
            "2": {"name": "Bob", "role": cfg.default_role},
        }
        self.auth_service.issue("alice")

    def list_users(self) -> list[dict[str, str]]:
        return [{"id": uid, **info} for uid, info in self._users.items()]  # type: ignore[misc]

    def get_user(self, user_id: str) -> dict[str, str] | None:
        return self._users.get(user_id)

    def create_user(self, name: str, role: str | None = None) -> dict[str, str]:
        uid = str(len(self._users) + 1)
        self._users[uid] = {"name": name, "role": role or "user"}
        return {"id": uid, **self._users[uid]}  # type: ignore[misc]
