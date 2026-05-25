"""Standalone notification service — simplest Canary Framework service unit.

A single ``@service`` with no dependencies: demonstrates that a lone ``@service``
is a fully-valid entry point for ``Canary()``.
"""

from __future__ import annotations

from standalone.config import NotifyConfig
from standalone.module import NotifyService as NotifyService

__all__ = ["NotifyConfig", "NotifyService"]
