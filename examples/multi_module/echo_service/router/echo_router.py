"""EchoRouter — HTTP endpoints for the standalone echo service."""

from __future__ import annotations

from typing import Any

from canary_framework import Context, on_init
from canary_framework.web.fastapi import get, post, router


@router(prefix="/echo")
class EchoRouter:
    """Route handler for echo endpoints (prefix: /echo)."""

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(object)
        self._greeting = getattr(cfg, "greeting", "hello")

    @get("/")
    async def greet(self) -> dict[str, str]:
        """GET /echo/ — return greeting."""
        return {"message": self._greeting}

    @get("/{text}")
    async def echo_get(self, text: str) -> dict[str, str]:
        """GET /echo/{text} — echo back the path parameter."""
        return {"echo": text}

    @post("/")
    async def echo_post(self, body: dict[str, Any]) -> dict[str, str]:
        """POST /echo/ — echo back the request body."""
        return {"echo": str(body.get("message", ""))}
