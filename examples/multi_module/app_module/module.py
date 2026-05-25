"""Module definition for the root AppModule.

Registers all three sub-modules/services as children, and declares its
own ``@web`` router for the health-check endpoint.
"""

from __future__ import annotations

from blog_service.module import BlogServiceModule
from standalone.module import NotifyService
from user_module.module import UserModule

from app_module.config import AppConfig
from app_module.router.health_router import HealthRouter
from canary_framework import module
from canary_framework.web.fastapi import web

__all__ = ["AppModule"]


@web(routers=[HealthRouter])
@module(
    name="AppModule",
    config=AppConfig,
    services=[NotifyService, UserModule, BlogServiceModule],
)
class AppModule:
    """Root application module — entry point for the full application.

    Composes:
        - ``NotifyService``     — standalone notification service (no deps)
        - ``UserModule``        — user-management module (AuthService + UserService)
        - ``BlogServiceModule``  — blog module (depends on NotifyService + UserService)

    Declares ``@web(routers=[HealthRouter])`` for the /api/health endpoint.
    """
