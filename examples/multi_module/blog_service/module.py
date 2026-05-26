"""Module definition for the blog service.

Routers are listed in ``services`` alongside other services — the Web engine
auto-discovers ``@router``-decorated classes via the Registry.
"""

from __future__ import annotations

from blog_service.config import BlogConfig
from blog_service.router.blog_router import BlogRouter
from blog_service.service.blog import BlogService
from canary_framework import module

__all__ = ["BlogServiceModule"]


@module(name="blog_service", config=BlogConfig, services=[BlogService, BlogRouter])
class BlogServiceModule:
    """Blog service module — wraps BlogService and exposes HTTP routes.

    Services contained:
        - ``BlogService`` — depends on NotifyService (standalone) and
          UserService (user_module).  Demonstrates cross-module dependency
          injection: deps reference services in other modules by class.
        - ``BlogRouter``  — HTTP endpoints for blog CRUD.
    """
