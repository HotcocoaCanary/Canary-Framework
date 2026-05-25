"""Blog service — depends on NotifyService and UserService, has own router.

Demonstrates cross-module dependency injection: a service inside this module
declares ``deps`` that reference services defined in other modules.
"""

from __future__ import annotations

from blog_service.config import BlogConfig
from blog_service.module import BlogServiceModule

__all__ = ["BlogConfig", "BlogServiceModule"]
