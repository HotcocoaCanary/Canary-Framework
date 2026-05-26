"""BlogService — depends on NotifyService (standalone) and UserService (user_module).

Demonstrates cross-module dependency resolution:
    deps=[NotifyService, UserService]

Framework resolves these by ``__cf_name__`` across the entire module tree.
"""

from __future__ import annotations

from standalone.module import NotifyService
from user_module.service.user import UserService

from blog_service.config import BlogConfig
from canary_framework import Context, on_init, on_start, service


@service(name="blog", deps=[NotifyService, UserService])
class BlogService:
    """Blog post management — cross-module dependency demonstration.

    Depends on:
        - ``NotifyService``  (standalone module) — notifies on new posts
        - ``UserService``     (user_module)      — resolves author info
    """

    def __init__(self) -> None:
        self._posts: list[dict[str, object]] = []

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(BlogConfig)
        author = cfg.default_author

        # self.notify_service  — injected as snake_case from deps=[NotifyService]
        notify: NotifyService = self.notify_service  # type: ignore[attr-defined]

        # self.user_service — injected as snake_case from deps=[UserService]
        user_svc: UserService = self.user_service  # type: ignore[attr-defined]
        author_info = user_svc.get_user("1")
        if author_info:
            author = author_info["name"]

        # Seed some demo posts
        for i in range(1, 4):
            pid = self.create_post(
                title=f"Demo Post {i}",
                content=f"This is the content of demo post #{i}.",
                author=author,
            )
            notify.notify("subscribers", f"New post published (id={pid})")

    @on_start
    def start(self) -> None:
        notify: NotifyService = self.notify_service  # type: ignore[attr-defined]
        notify.notify("system", "BlogService started")

    def create_post(self, title: str, content: str, author: str) -> str:
        pid = str(len(self._posts) + 1)
        self._posts.append({
            "id": pid,
            "title": title,
            "content": content,
            "author": author,
        })
        return pid

    def list_posts(self) -> list[dict[str, object]]:
        return list(self._posts)

    def get_post(self, post_id: str) -> dict[str, object] | None:
        for p in self._posts:
            if p["id"] == post_id:
                return p
        return None

    @property
    def post_count(self) -> int:
        return len(self._posts)
