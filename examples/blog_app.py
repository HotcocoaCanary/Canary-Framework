#!/usr/bin/env python3
"""Complete Canary Framework blog application example.

Demonstrates:
- Pydantic-based configuration with @config + CanaryConfig
- Explicit base class inheritance (ServiceBase, ModuleBase, RouterBase)
- Annotation-based dependency injection
- Lifecycle hooks (@after_init, @before_shutdown)
- Full CRUD router with path/query/body parameter binding
- Auto-generated OpenAPI docs (Swagger + ReDoc)
- Standalone execution with uvicorn
"""

import asyncio

from pydantic import BaseModel, Field

from canary_framework import (
    after_init,
    before_shutdown,
    config,
    delete,
    get,
    module,
    post,
    put,
    router,
    service,
)
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase
from canary_framework.core.service import ServiceBase
from canary_framework.common.config import CanaryConfig

# ---- Pydantic Models ----

class PostCreate(BaseModel):
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")


class PostResponse(BaseModel):
    id: int = Field(description="Post ID")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")


# ---- Services ----

@service()
class Database(ServiceBase):
    """Simulated database with lifecycle hooks."""

    def __init__(self):
        super().__init__()
        self.connected = False
        self._storage: dict[int, dict] = {}

    @after_init
    async def connect(self):
        self.connected = True
        print("[Database] Connected")

    @before_shutdown
    async def disconnect(self):
        self.connected = False
        print("[Database] Disconnected")

    async def create(self, item: dict) -> dict:
        item_id = len(self._storage) + 1
        item["id"] = item_id
        self._storage[item_id] = item
        return item

    async def get_all(self) -> list[dict]:
        return list(self._storage.values())

    async def get_one(self, item_id: int) -> dict | None:
        return self._storage.get(item_id)

    async def update(self, item_id: int, data: dict) -> dict | None:
        if item_id in self._storage:
            self._storage[item_id].update(data)
            return self._storage[item_id]
        return None

    async def delete(self, item_id: int) -> bool:
        return self._storage.pop(item_id, None) is not None


@service()
class PostService(ServiceBase):
    """Business logic for blog posts. Depends on Database via annotation."""

    db: Database  # Auto-injected by the framework

    async def create_post(self, post: PostCreate) -> dict:
        return await self.db.create(post.model_dump())

    async def list_posts(self) -> list[dict]:
        return await self.db.get_all()

    async def get_post(self, post_id: int) -> dict | None:
        return await self.db.get_one(post_id)

    async def update_post(self, post_id: int, post: PostCreate) -> dict | None:
        return await self.db.update(post_id, post.model_dump())

    async def delete_post(self, post_id: int) -> bool:
        return await self.db.delete(post_id)


# ---- Router ----

@router(prefix="/api/posts", tags=["Posts"])
class PostRouter(RouterBase):
    """REST API for blog posts. Depends on PostService via annotation."""

    posts: PostService  # Auto-injected

    @get("/?page={page}&limit={limit}", summary="List posts with pagination")
    async def list_posts(self, page: int = 1, limit: int = 10) -> dict:
        all_posts = await self.posts.list_posts()
        start = (page - 1) * limit
        return {"posts": all_posts[start : start + limit], "page": page, "limit": limit}

    @get("/{post_id}", summary="Get a post", response_model=PostResponse)
    async def get_post(self, post_id: int):
        post = await self.posts.get_post(post_id)
        if post:
            return post
        return {"error": "Not found"}, 404

    @post("/", summary="Create a post", request_model=PostCreate, response_model=PostResponse)
    async def create_post(self, body: PostCreate):
        return await self.posts.create_post(body), 201

    @put("/{post_id}", summary="Update a post", request_model=PostCreate, response_model=PostResponse)
    async def update_post(self, post_id: int, body: PostCreate):
        post = await self.posts.update_post(post_id, body)
        if post:
            return post
        return {"error": "Not found"}, 404

    @delete("/{post_id}", summary="Delete a post")
    async def delete_post(self, post_id: int):
        ok = await self.posts.delete_post(post_id)
        return {"deleted": ok}


# ---- Configuration ----

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8001
    openapi_title: str = "Blog API"


# ---- Module (Application) ----

@module(services=[AppConfig, Database, PostService, PostRouter])
class BlogApp(ModuleBase):
    """Main application module. Composes all services and routers."""


# ---- Entry Point ----

async def setup():
    app = BlogApp()
    await app.init()
    return app


if __name__ == "__main__":
    import uvicorn

    app = asyncio.run(setup())
    config = getattr(app, "AppConfig", None)
    host = config.host if config else "0.0.0.0"
    port = config.port if config else 8001
    uvicorn.run(app, host=host, port=port, lifespan="on")