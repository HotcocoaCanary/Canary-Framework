"""User module — multi-service module with router and config.

Demonstrates a ``@module`` that composes multiple ``@service`` classes,
has its own ``@config``, and exposes HTTP routes via ``@web`` + ``@router``.
"""

from __future__ import annotations

from user_module.config import UserModuleConfig
from user_module.module import UserModule

__all__ = ["UserModule", "UserModuleConfig"]
