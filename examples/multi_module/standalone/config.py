"""NotifyService config — self-contained config for the standalone service."""

from __future__ import annotations

from canary_framework import config


@config
class NotifyConfig:
    """Configuration for the standalone notification service."""

    enabled: bool = True
    provider: str = "console"
    rate_limit: int = 100
