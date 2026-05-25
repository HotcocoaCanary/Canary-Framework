"""Module definition for the user-management module.

Demonstrates ``@web()`` and ``@module`` stack: ``@web`` (closer to class)
runs first, then ``@module`` stores the module metadata.
"""

from __future__ import annotations

from canary_framework import module
from canary_framework.web.fastapi import web
from user_module.config import UserModuleConfig
from user_module.router.user_router import UserRouter
from user_module.service.auth import AuthService
from user_module.service.user import UserService

__all__ = ["UserModule"]


@web(routers=[UserRouter])
@module(name="user_module", config=UserModuleConfig, services=[AuthService, UserService])
class UserModule:
    """User management module — groups AuthService and UserService together.

    Declares ``@web(routers=[UserRouter])`` to expose user CRUD endpoints.
    Child services inherit ``UserModuleConfig`` automatically.
    """
