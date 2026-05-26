"""Module definition for the user-management module."""

from __future__ import annotations

from canary_framework import module
from user_module.config import UserModuleConfig
from user_module.router.user_router import UserRouter
from user_module.service.auth import AuthService
from user_module.service.user import UserService

__all__ = ["UserModule"]


@module(
    name="user_module", config=UserModuleConfig, services=[AuthService, UserService, UserRouter]
)
class UserModule:
    """User management module — groups AuthService, UserService, and UserRouter.

    Child services inherit ``UserModuleConfig`` automatically.
    The Web engine auto-discovers ``UserRouter`` via the Registry.
    """
