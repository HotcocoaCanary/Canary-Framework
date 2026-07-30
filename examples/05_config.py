"""Example 5: Configuration via @config + CanaryConfig.

A fully customized configuration injected via DI.
Demonstrates: @config, CanaryConfig, config ownership, custom OpenAPI
metadata, CDN URLs, and log level.
"""

from __future__ import annotations

import asyncio
from typing import Literal

import uvicorn
from pydantic import Field

from canary_framework import config, get, module, router
from canary_framework.common import CanaryConfig
from canary_framework.core import ModuleBase, RouterBase


@config()
class AppConfig(CanaryConfig):
    """Custom configuration for the application."""

    openapi_title: str = "My Custom API"
    openapi_version: str = "2.0.0"
    openapi_description: str = "A customized Canary Framework API"
    openapi_servers: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"url": "http://localhost:8080", "description": "Local"},
            {"url": "https://api.example.com", "description": "Production"},
        ]
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"


@router(prefix="/api")
class ApiRouter(RouterBase):
    @get("/info")
    async def info(self) -> dict[str, str]:
        config = self.config
        assert config is not None
        return {
            "framework": "Canary",
            "version": config.openapi_version,
            "log_level": config.log_level,
        }


@module(config=AppConfig, children=(ApiRouter,))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    uvicorn.run(application, lifespan="on")
