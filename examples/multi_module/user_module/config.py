"""User module configuration."""

from __future__ import annotations

from canary_framework import config


@config
class UserModuleConfig:
    """Configuration for the user-management module."""

    default_role: str = "user"
    token_expire_minutes: int = 60
    max_users: int = 1000
