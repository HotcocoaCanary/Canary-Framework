"""Echo service configuration."""

from __future__ import annotations

from canary_framework import config


@config
class EchoConfig:
    """Configuration for the standalone echo service."""

    # ── Business ──
    greeting: str = "Hello from standalone EchoService"
    echo_prefix: str = "[echo]"

    # ── WebCanary (prefix convention) ──
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8001
    uvicorn_log_level: str = "info"
    fastapi_title: str = "Echo Service (Standalone)"
    fastapi_version: str = "0.1.0"
