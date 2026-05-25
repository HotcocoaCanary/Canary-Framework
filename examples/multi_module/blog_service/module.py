"""Module definition for the blog service.

Demonstrates a ``@module`` wrapping a single ``@service`` (BlogService)
together with a ``@web`` + ``@router`` declaration.
"""

from __future__ import annotations

from blog_service.config import BlogConfig
from blog_service.router.blog_router import BlogRouter
from blog_service.service.blog import BlogService
from canary_framework import module
from canary_framework.web.fastapi import web

__all__ = ["BlogServiceModule"]


@web(routers=[BlogRouter])
@module(name="blog_service", config=BlogConfig, services=[BlogService])
class BlogServiceModule:
    """Blog service module — wraps BlogService and exposes HTTP routes.

    Services contained:
        - ``BlogService`` — depends on NotifyService (standalone) and
          UserService (user_module).  Demonstrates cross-module dependency
          injection: deps reference services in other modules by class.
    """
