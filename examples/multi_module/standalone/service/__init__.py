"""Service-implementation layer for the NotifyService.

The ``@service`` class itself lives in :mod:`standalone.module` — this
directory contains the business-logic helpers it delegates to.
"""

from __future__ import annotations

from .notify import NotifyService

__all__ = ["NotifyService"]
