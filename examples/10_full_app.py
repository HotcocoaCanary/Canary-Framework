"""Example 10: Complete Realistic Application.

A blog API with:
- Configuration (@config + CanaryConfig)
- Three sub-modules (auth, posts, comments)
- DI across module boundaries
- Lifecycle hooks (DB setup, caching)
- Request/response validation (Pydantic)
- Swagger/ReDoc with custom metadata

Architecture:
    App (root module)
    ├── AppConfig
    ├── Database (shared service)
    ├── AuthModule → AuthService
    ├── PostModule → PostService
    └── CommentModule → CommentService
"""

import uvicorn
from pydantic import BaseModel, Field

from canary_framework import (
    before_shutdown,
    config,
    module,
    service,
)
from canary_framework.common.config import CanaryConfig
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


# ── Configuration ────────────────────────────────────────
@config()
class AppConfig(CanaryConfig):
    openapi_title: str = "Blog API"
    openapi_version: str = "1.0.0"
    openapi_description: str = "A full-featured blog API built with Canary Framework"
    log_level: str = "INFO"


# ── Shared Database Service ──────────────────────────────
@service()
class Database(ServiceBase):
    """Simulated database with lifecycle management."""

    async def connect(self):
        self._storage: dict[str, list[dict]] = {
            "users": [],
            "posts": [],
            "comments": [],
        }
        print("[DB] Connected, storage initialized")

    @before_shutdown
    async def disconnect(self):
        self._storage.clear()
        print("[DB] Disconnected, storage cleared")

    def all(self, table: str) -> list[dict]:
        return self._storage.get(table, [])

    def insert(self, table: str, item: dict) -> dict:
        self._storage[table].append(item)
        return item

    def next_id(self, table: str) -> int:
        return len(self._storage[table]) + 1


# ── Pydantic Models ──────────────────────────────────────
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


# ── Auth Module ──────────────────────────────────────────
@service()
class AuthService(ServiceBase):
    router = Router(prefix="/auth", tags=["auth"])
    db: Database

    async def seed_admin(self):
        self.db.insert("users", {"id": 1, "username": "admin", "email": "admin@blog.com"})
        print("[Auth] Admin user seeded")

    @router.post("/register", summary="Register a new user", response_model=User)
    async def register(self, user: CreateUser) -> dict:
        new_id = self.db.next_id("users")
        new_user = {"id": new_id, "username": user.username, "email": user.email}
        return self.db.insert("users", new_user)

    @router.get("/users", summary="List all users", response_model=list[User])
    async def list_users(self) -> list[dict]:
        return self.db.all("users")


@module(services=[AuthService])
class AuthModule(ModuleBase):
    pass


# ── Post Module ──────────────────────────────────────────
@service()
class PostService(ServiceBase):
    router = Router(prefix="/posts", tags=["posts"])
    db: Database

    @router.get("/", summary="List all posts", response_model=list[Post])
    async def list_posts(self) -> list[dict]:
        return self.db.all("posts")

    @router.get("/{post_id}", summary="Get a post by ID", response_model=Post)
    async def get_post(self, post_id: int) -> dict | tuple:
        posts = self.db.all("posts")
        for p in posts:
            if p["id"] == post_id:
                return p
        return {"error": "Not found"}, 404

    @router.post("/", summary="Create a new post", response_model=Post)
    async def create_post(self, post: CreatePost) -> dict:
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


@module(services=[PostService])
class PostModule(ModuleBase):
    pass


# ── Comment Module ───────────────────────────────────────
@service()
class CommentService(ServiceBase):
    router = Router(prefix="/comments", tags=["comments"])
    db: Database

    @router.get("/post/{post_id}", summary="Get comments for a post", response_model=list[Comment])
    async def get_comments(self, post_id: int) -> list[dict]:
        return [c for c in self.db.all("comments") if c["post_id"] == post_id]

    @router.post("/post/{post_id}", summary="Add a comment to a post", response_model=Comment)
    async def add_comment(self, post_id: int, comment: CreateComment) -> dict:
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


@module(services=[CommentService])
class CommentModule(ModuleBase):
    pass


# ── Root Module ──────────────────────────────────────────
@module(config=AppConfig, services=[Database, AuthModule, PostModule, CommentModule])
class App(ModuleBase):
    router = Router(tags=["system"])

    @router.get("/", summary="API root")
    async def root(self) -> dict:
        return {
            "app": "Blog API",
            "version": "0.5.0",
            "docs": "/docs",
        }


if __name__ == "__main__":
    app = App()
    app.init()

    print("\n=== Blog API Started ===")
    print("  Root:        http://127.0.0.1:8000/")
    print("  Swagger UI:  http://127.0.0.1:8000/docs")
    print("  ReDoc:       http://127.0.0.1:8000/redoc")
    print("  OpenAPI:     http://127.0.0.1:8000/openapi.json")
    print("  Auth:        http://127.0.0.1:8000/auth/users")
    print("  Posts:       http://127.0.0.1:8000/posts/")
    print("  Comments:    http://127.0.0.1:8000/comments/post/1")

    uvicorn.run(app, lifespan="on")
