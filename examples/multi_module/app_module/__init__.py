"""AppModule — root module composing all sub-modules / services.

Registers the standalone service, user module, and blog service into a
single application tree.  Has its own health-check router.
"""

from __future__ import annotations

from app_module.config import AppConfig
from app_module.module import AppModule as AppModule

__all__ = ["AppConfig", "AppModule"]
