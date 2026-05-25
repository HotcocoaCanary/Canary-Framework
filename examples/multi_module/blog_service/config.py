"""Blog service configuration."""

from __future__ import annotations

from canary_framework import config


@config
class BlogConfig:
    """Configuration for the blog service."""

    default_author: str = "anonymous"
    posts_per_page: int = 10
    enable_comments: bool = True
