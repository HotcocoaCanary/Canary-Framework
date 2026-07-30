"""Example 10: Complete Realistic Application.

A blog API with:
- Configuration (@config + CanaryConfig)
- Three sub-domains (auth, posts, comments)
- DI across module boundaries
- Lifecycle management (DB setup, caching)
- Request/response validation (Pydantic)
- Swagger/ReDoc with custom metadata

Architecture:
    App (root module)
    ├── Database (shared service; root owns AppConfig)
    ├── AuthRouter → AuthService
    ├── PostRouter → PostService
    └── CommentRouter → CommentService
"""

from __future__ import annotations

import asyncio
from typing import Literal, cast

import uvicorn
from pydantic import BaseModel, Field

from canary_framework import config, get, module, post, router, service
from canary_framework.common import CanaryConfig
from canary_framework.core import ModuleBase, RouterBase, ServiceBase


@config()
class AppConfig(CanaryConfig):
    openapi_title: str = "Blog API"
    openapi_version: str = "1.0.0"
    openapi_description: str = "A full-featured blog API built with Canary Framework"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    openapi_security_schemes: dict[str, dict[str, object]] = Field(
        default_factory=lambda: cast(
            dict[str, dict[str, object]],
            {"apiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
        )
    )


@service()
class Database(ServiceBase):
    """Simulated database with lifecycle management."""

    async def on_init(self) -> None:
        self._storage: dict[str, list[dict[str, object]]] | None = None
        print("[DB] Initialized, storage prepared")

    async def on_startup(self) -> None:
        self._storage = {"users": [], "posts": [], "comments": []}
        print("[DB] Connected, storage initialized")

    async def on_shutdown(self) -> None:
        if self._storage is not None:
            self._storage.clear()
        print("[DB] Disconnected, storage cleared")

    def _require_storage(self) -> dict[str, list[dict[str, object]]]:
        assert self._storage is not None
        return self._storage

    def all(self, table: str) -> list[dict[str, object]]:
        return self._require_storage().get(table, [])

    def insert(self, table: str, item: dict[str, object]) -> dict[str, object]:
        storage = self._require_storage()
        storage[table].append(item)
        return item

    def next_id(self, table: str) -> int:
        return len(self._require_storage()[table]) + 1


class User(BaseModel):
    id: int
    username: str = Field(min_length=3, max_length=30)
    email: str


class CreateUser(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str


class Post(BaseModel):
    id: int
    title: str
    content: str
    author: str


class CreatePost(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    author: str


class Comment(BaseModel):
    id: int
    post_id: int
    author: str
    body: str


class CreateComment(BaseModel):
    author: str
    body: str = Field(min_length=1)


@service()
class AuthService(ServiceBase):
    db: Database

    async def seed_admin(self) -> None:
        self.db.insert("users", {"id": 1, "username": "admin", "email": "admin@blog.com"})
        print("[Auth] Admin user seeded")

    def register(self, user: CreateUser) -> dict[str, object]:
        new_id = self.db.next_id("users")
        new_user = {"id": new_id, "username": user.username, "email": user.email}
        return self.db.insert("users", new_user)

    def list_users(self) -> list[dict[str, object]]:
        return self.db.all("users")


@router(prefix="/auth", tags=("auth",), security=("apiKeyAuth",))
class AuthRouter(RouterBase):
    auth: AuthService

    @post("/register", summary="Register a new user", response_model=User)
    async def register(self, user: CreateUser) -> dict[str, object]:
        return self.auth.register(user)

    @get("/users", summary="List all users", response_model=list[User])
    async def list_users(self) -> list[dict[str, object]]:
        return self.auth.list_users()


@service()
class PostService(ServiceBase):
    db: Database

    def list_posts(self) -> list[dict[str, object]]:
        return self.db.all("posts")

    def get_post(self, post_id: int) -> dict[str, object] | tuple[dict[str, str], int]:
        posts = self.db.all("posts")
        for record in posts:
            if record["id"] == post_id:
                return record
        return {"error": "Not found"}, 404

    def create_post(self, post: CreatePost) -> dict[str, object]:
        new_id = self.db.next_id("posts")
        return self.db.insert(
            "posts",
            {
                "id": new_id,
                "title": post.title,
                "content": post.content,
                "author": post.author,
            },
        )


@router(prefix="/posts", tags=("posts",), security=("apiKeyAuth",))
class PostRouter(RouterBase):
    posts: PostService

    @get("/", summary="List all posts", response_model=list[Post])
    async def list_posts(self) -> list[dict[str, object]]:
        return self.posts.list_posts()

    @get("/{post_id}", summary="Get a post by ID", response_model=Post)
    async def get_post(self, post_id: int) -> dict[str, object] | tuple[dict[str, str], int]:
        return self.posts.get_post(post_id)

    @post("/", summary="Create a new post", response_model=Post)
    async def create_post(self, post: CreatePost) -> dict[str, object]:
        return self.posts.create_post(post)


@service()
class CommentService(ServiceBase):
    db: Database

    def get_comments(self, post_id: int) -> list[dict[str, object]]:
        return [comment for comment in self.db.all("comments") if comment["post_id"] == post_id]

    def add_comment(self, post_id: int, comment: CreateComment) -> dict[str, object]:
        new_id = self.db.next_id("comments")
        return self.db.insert(
            "comments",
            {
                "id": new_id,
                "post_id": post_id,
                "author": comment.author,
                "body": comment.body,
            },
        )


@router(prefix="/comments", tags=("comments",), security=("apiKeyAuth",))
class CommentRouter(RouterBase):
    comments: CommentService

    @get("/post/{post_id}", summary="Get comments for a post", response_model=list[Comment])
    async def get_comments(self, post_id: int) -> list[dict[str, object]]:
        return self.comments.get_comments(post_id)

    @post("/post/{post_id}", summary="Add a comment to a post", response_model=Comment)
    async def add_comment(self, post_id: int, comment: CreateComment) -> dict[str, object]:
        return self.comments.add_comment(post_id, comment)


@module(config=AppConfig, prefix="/api", children=(Database, AuthRouter, PostRouter, CommentRouter))
class App(ModuleBase):
    async def on_init(self) -> None:
        return None


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())

    print("\n=== Blog API Started ===")
    print("  API prefix:  http://127.0.0.1:8000/api")
    print("  Swagger UI:  http://127.0.0.1:8000/docs")
    print("  ReDoc:       http://127.0.0.1:8000/redoc")
    print("  OpenAPI:     http://127.0.0.1:8000/openapi.json")
    print("  Auth:        http://127.0.0.1:8000/api/auth/users")
    print("  Posts:       http://127.0.0.1:8000/api/posts/")
    print("  Comments:    http://127.0.0.1:8000/api/comments/post/1")

    uvicorn.run(application, lifespan="on")
