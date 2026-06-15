"""Example 5: Configuration via @config + CanaryConfig.

A fully customized configuration injected via DI.
Demonstrates: @config, CanaryConfig, DI for config,
custom OpenAPI metadata, CDN URLs, log level.
"""

import uvicorn

from canary_framework import config, module, service
from canary_framework.common.config import CanaryConfig
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


# ── Custom configuration ─────────────────────────────────
@config()
class AppConfig(CanaryConfig):
    """Custom configuration for the application."""

    openapi_title: str = "My Custom API"
    openapi_version: str = "2.0.0"
    openapi_description: str = "A customized Canary Framework API"
    openapi_servers: list[dict] = [
        {"url": "http://localhost:8080", "description": "Local"},
        {"url": "https://api.example.com", "description": "Production"},
    ]
    log_level: str = "DEBUG"


# ── Service ──────────────────────────────────────────────
@service()
class Api(ServiceBase):
    router = Router(prefix="/api")

    @router.get("/info")
    async def info(self) -> dict:
        return {"framework": "Canary", "version": "0.5.0"}


# ── Root Module ──────────────────────────────────────────
@module(config=AppConfig, services=[Api])
class App(ModuleBase):
    pass


if __name__ == "__main__":
    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
