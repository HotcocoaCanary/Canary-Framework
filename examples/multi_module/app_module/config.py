"""Root application configuration.

For ``WebCanary``, fields prefixed ``uvicorn_*`` are routed to Uvicorn,
``fastapi_*`` to FastAPI, and the rest remain as business configuration.
"""

from __future__ import annotations

from canary_framework import config


@config
class AppConfig:
    """Top-level application configuration combining business + web settings."""

    # ── Business ──
    app_name: str = "Canary Multi-Module Demo"
    env: str = "development"
    debug: bool = True

    # ── WebCanary (split by prefix convention) ──
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    uvicorn_log_level: str = "info"
    fastapi_title: str = "Canary Multi-Module API"
    fastapi_version: str = "0.1.0"
    fastapi_docs_url: str = "/docs"
