"""HealthRouter — health-check and meta endpoints at root level."""

from __future__ import annotations

from canary_framework import Context, on_init
from canary_framework import __version__ as cf_version
from canary_framework.web.fastapi import get, router


@router(prefix="/api")
class HealthRouter:
    """Root-level health and info endpoints (prefix: /api)."""

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(object)
        self._app_name = getattr(cfg, "app_name", "unknown")

    @get("/")
    async def health(self) -> dict[str, str]:
        """GET /api/ — framework and application health check."""
        return {
            "status": "healthy",
            "framework": f"canary v{cf_version}",
            "app": self._app_name,
        }
