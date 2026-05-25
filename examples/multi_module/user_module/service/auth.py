"""AuthService — handles authentication tokens."""

from __future__ import annotations

from canary_framework import Context, on_init, service
from user_module.config import UserModuleConfig


@service(name="auth")
class AuthService:
    """Authentication service — token generation and validation."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}
        self._token_expire: int = 60

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.config_as(UserModuleConfig)
        self._token_expire = cfg.token_expire_minutes
        self._tokens["admin"] = "admin-token"

    def validate(self, token: str) -> str | None:
        for user, t in self._tokens.items():
            if t == token:
                return user
        return None

    def issue(self, username: str) -> str:
        token = f"tok-{username}-{len(self._tokens)}"
        self._tokens[username] = token
        return token
