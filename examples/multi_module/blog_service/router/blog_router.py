"""BlogRouter — HTTP routes for blog operations.

Demonstrates ``@router(prefix=...)`` with ``@get``, ``@post``, ``@put``, ``@patch``.
"""

from __future__ import annotations

from typing import Any

from blog_service.service.blog import BlogService
from canary_framework import Context
from canary_framework.web.fastapi import get, patch, post, put, router


@router(prefix="/api/blog")
class BlogRouter:
    """Route handler for blog endpoints (prefix: /api/blog)."""

    def __init__(self, ctx: Context) -> None:
        self._svc = ctx.resolve(BlogService)

    @get("/")
    async def list_posts(self) -> list[dict[str, object]]:
        """GET /api/blog/ — list all blog posts."""
        return self._svc.list_posts()

    @get("/{post_id}")
    async def get_post(self, post_id: str) -> dict[str, str | object] | None:
        """GET /api/blog/{post_id} — get a single post."""
        post = self._svc.get_post(post_id)
        if post is None:
            return {"detail": "not found"}
        return post

    @post("/")
    async def create_post(self, body: dict[str, Any]) -> dict[str, str]:
        """POST /api/blog/ — create a new post."""
        pid = self._svc.create_post(
            title=str(body.get("title", "untitled")),
            content=str(body.get("content", "")),
            author=str(body.get("author", "anonymous")),
        )
        return {"id": pid}

    @put("/{post_id}")
    async def update_post(self, post_id: str, body: dict[str, Any]) -> dict[str, str]:
        """PUT /api/blog/{post_id} — update an existing post."""
        post = self._svc.get_post(post_id)
        if post is None:
            return {"detail": "not found"}
        post["title"] = body.get("title", post["title"])
        post["content"] = body.get("content", post["content"])
        return {"id": post_id, "updated": True}

    @patch("/{post_id}")
    async def patch_post(self, post_id: str, body: dict[str, Any]) -> dict[str, str]:
        """PATCH /api/blog/{post_id} — partially update a post."""
        post = self._svc.get_post(post_id)
        if post is None:
            return {"detail": "not found"}
        if "title" in body:
            post["title"] = body["title"]
        if "content" in body:
            post["content"] = body["content"]
        return {"id": post_id, "patched": True}
