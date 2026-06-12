# Canary Framework

Lightweight, decorator-driven Python async service framework. Core philosophy: **Service is the smallest unit. Modules compose services. Modules themselves are services.**

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  @config(CanaryConfig)  ——  @module(services=[...])          │
│      auto-discovered          composes & orchestrates         │
├─────────────────────────────────────────────────────────────┤
│  @service(ServiceBase)                   Router(prefix=...)  │
│    business logic                         class attribute    │
│    lifecycle hooks                        auto OpenAPI       │
├─────────────────────────────────────────────────────────────┤
│  Engine: Registry · Injector · Hooks · OpenAPI · Params      │
├─────────────────────────────────────────────────────────────┤
│  Starlette / ASGI (uvicorn)                                  │
└─────────────────────────────────────────────────────────────┘
```

## Core Concepts

### Service — `@service()` + `ServiceBase`

The smallest unit. Encapsulates business logic with lifecycle hooks and annotation-driven dependency injection.

```python
from canary_framework import service, after_init, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    db_url: str = "sqlite:///app.db"

    @after_init
    async def connect(self):
        self.connection = await create_pool(self.db_url)

    @before_shutdown
    async def disconnect(self):
        await self.connection.close()

    async def query(self, sql: str):
        return await self.connection.execute(sql)
```

### Module — `@module(services=[...])` + `ModuleBase`

Orchestrates child services through their lifecycle. Mounts child ASGI apps. Modules themselves are services.

```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

@module(services=[Database, Auth, Posts])
class BlogApp(ModuleBase):
    pass
```

### Router — `Router(prefix=..., tags=...)` class attribute

HTTP routing via a `Router` class attribute on any service. Use `@router.get()` / `@router.post()` for route handlers with auto-bound path params, query params, and request body. Auto-generates OpenAPI 3.0.3 documentation.

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Posts(ServiceBase):
    db: Database
    router = Router(prefix="/api/posts", tags=["Posts"])

    @router.get("/")
    async def list_posts(self, page: int = 1, limit: int = 10):
        return await self.db.query(f"SELECT * FROM posts LIMIT {limit} OFFSET {(page-1)*limit}")

    @router.get("/{post_id}")
    async def get_post(self, post_id: int):
        return await self.db.query(f"SELECT * FROM posts WHERE id={post_id}")

    @router.post("/", request_model=PostCreate)
    async def create_post(self, body: PostCreate):
        return await self.db.create_post(body), 201
```

### Configuration — `@config` + `CanaryConfig`

Pydantic-based configuration with sensible defaults and type validation. Extra fields are allowed.

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    openapi_title: str = "My Blog API"
    log_level: str = "DEBUG"
```

### Dependency Injection

Annotation-driven DI: declare dependencies with type annotations, and the framework resolves them via `resolve_deps()` + `topological_sort()` (Kahn's algorithm). Dependencies are injected using `setattr(instance, attr_name, dep_instance)` — the annotation key name becomes the attribute name.

```python
@service()
class Auth(ServiceBase):
    db: Database   # Auto-injected as self.db
    cache: Cache   # Auto-injected as self.cache
```

## Quick Example

A complete minimal working example: Database service + PostService + a service with Router + BlogApp module + AppConfig + entry point.

```python
# main.py
from pydantic import BaseModel
from canary_framework import (
    service, module, config,
    before_shutdown, after_init,
)
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.common.config import CanaryConfig

# ---- Models ----
class PostCreate(BaseModel):
    title: str
    content: str

# ---- Services ----
@service()
class Database(ServiceBase):
    def __init__(self):
        self.connected = False

    @after_init
    async def connect(self):
        self.connected = True

    @before_shutdown
    async def disconnect(self):
        self.connected = False

    async def query(self, sql: str):
        return f"Executed: {sql}"

@service()
class PostService(ServiceBase):
    db: Database

    def __init__(self):
        self.posts = []

    @after_init
    async def seed(self):
        self.posts = [{"id": 1, "title": "Hello", "content": "World"}]

    async def list_posts(self):
        return self.posts

    async def get_post(self, post_id: int):
        return next((p for p in self.posts if p["id"] == post_id), None)

    async def create_post(self, data: dict):
        data["id"] = len(self.posts) + 1
        self.posts.append(data)
        return data

# ---- Service with Router ----
@service()
class PostRouter(ServiceBase):
    db: Database
    posts: PostService
    router = Router(prefix="/api/posts", tags=["Posts"])

    @router.get("/")
    async def list_posts(self, page: int = 1, limit: int = 10):
        return {"posts": await self.posts.list_posts()}

    @router.get("/{post_id}")
    async def get_post(self, post_id: int):
        post = await self.posts.get_post(post_id)
        return post if post else ({"error": "Not found"}, 404)

    @router.post("/", request_model=PostCreate)
    async def create_post(self, body: PostCreate):
        return await self.posts.create_post(body.model_dump()), 201

# ---- Module & Config ----
@module(services=[AppConfig, Database, PostService, PostRouter])
class BlogApp(ModuleBase):
    config: AppConfig

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8000
    openapi_title: str = "Blog API"
    log_level: str = "DEBUG"

async def setup():
    app = BlogApp()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn
    app = asyncio.run(setup())
    uvicorn.run(app, host="0.0.0.0", port=8000, lifespan="on")
```

## Installation

```bash
pip install canary-framework
```

## Package Structure

```
src/canary_framework/
├── common/
│   ├── config.py
│   ├── types.py
│   ├── routing.py
│   └── errors.py
├── core/
│   ├── module/
│   │   └── _base.py       # ModuleBase
│   ├── service/
│   │   ├── _base.py       # ServiceBase
│   │   └── _hooks.py      # Lifecycle hook invocation
│   └── router/
│       ├── _base.py       # Router + RouteInfo
│       └── _utils.py      # Route handler building
├── decorators/
│   ├── service.py
│   ├── module.py
│   ├── config.py
│   └── lifecycle.py
└── engine/
    ├── registry.py
    ├── dependencies.py
    ├── openapi.py
    ├── params.py
    └── logging.py
```

## Design Principles

1. **Decorator-driven** — Code is configuration; decorators transform plain classes
2. **Async-first** — Built on async/await, ASGI/Starlette
3. **Annotation-based DI** — Dependencies declared with type hints, resolved automatically
4. **Explicit inheritance** — Classes inherit from framework base classes (ServiceBase, ModuleBase)
5. **Automatic naming** — `ClassName` + suffix (`Service`, `Module`); routers are services, no separate naming convention needed
6. **Composability** — Modules compose services; modules are themselves services

## Next Steps

- [Quickstart](./quickstart.md)
- [Configuration](./configuration.md)
- [Services](./services.md)
- [Modules](./modules.md)
- [Routers & HTTP](./web.md)
- [Dependency Injection](./dependency-injection.md)
- [Lifecycle](./lifecycle.md)
- [Architecture & Internals](./core.md)
- [API Reference](./api-reference.md)
