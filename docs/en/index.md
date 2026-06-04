# Canary Framework

Lightweight, decorator-driven Python async service framework. Core philosophy: **Service is the smallest unit. Modules compose services. Modules themselves are services.**

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  @config(CanaryConfig)  ——  @module(services=[...])          │
│       configures             composes & orchestrates         │
├─────────────────────────────────────────────────────────────┤
│  @service(ServiceBase)              @router(RouterBase)      │
│    business logic                     HTTP routing           │
│    lifecycle hooks                    auto OpenAPI            │
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
from canary_framework import service, after_config, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    db_url: str = "sqlite:///app.db"

    @after_config
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

### Router — `@router(prefix=...)` + `RouterBase`

HTTP routing with auto-bound path params, query params, and request body. Auto-generates OpenAPI 3.0.3 documentation.

```python
from canary_framework import router, get, post
from canary_framework.core.router import RouterBase

@router(prefix="/api/posts", tags=["Posts"])
class Posts(RouterBase):
    db: Database

    @get("/")
    async def list_posts(self, page: int = 1, limit: int = 10):
        return await self.db.query(f"SELECT * FROM posts LIMIT {limit} OFFSET {(page-1)*limit}")

    @get("/{post_id}")
    async def get_post(self, post_id: int):
        return await self.db.query(f"SELECT * FROM posts WHERE id={post_id}")

    @post("/", request_model=PostCreate)
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

A complete minimal working example: Database service + PostService + PostRouter + BlogApp module + AppConfig + entry point.

```python
# main.py
from pydantic import BaseModel
from canary_framework import (
    service, module, router, config, get, post,
    after_config, before_shutdown, after_init,
)
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase
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

    @after_config
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

# ---- Router ----
@router(prefix="/api/posts", tags=["Posts"])
class PostRouter(RouterBase):
    db: Database
    posts: PostService

    @get("/")
    async def list_posts(self, page: int = 1, limit: int = 10):
        return {"posts": await self.posts.list_posts()}

    @get("/{post_id}")
    async def get_post(self, post_id: int):
        post = await self.posts.get_post(post_id)
        return post if post else ({"error": "Not found"}, 404)

    @post("/", request_model=PostCreate)
    async def create_post(self, body: PostCreate):
        return await self.posts.create_post(body.model_dump()), 201

# ---- Module & Config ----
@module(services=[Database, PostService, PostRouter])
class BlogApp(ModuleBase):
    pass

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8000
    openapi_title: str = "Blog API"
    log_level: str = "DEBUG"

async def setup():
    cfg = AppConfig()
    app = BlogApp()
    await app.configure(cfg)
    await app.init()
    return app, cfg

if __name__ == "__main__":
    import asyncio
    import uvicorn
    app, cfg = asyncio.run(setup())
    uvicorn.run(app, host=cfg.host, port=cfg.port, lifespan="on")
```

## Installation

```bash
pip install canary-framework
```

## Package Structure

```
src/canary_framework/
├── common/              # Types, errors, routing, config
│   ├── config.py        # CanaryConfig (Pydantic-based configuration)
│   ├── types.py         # Enums, dataclasses, markers, resolve_deps()
│   ├── routing.py       # Route path parsing
│   └── errors.py        # Framework exceptions
├── core/                # Base classes
│   ├── service.py       # ServiceBase — lifecycle, ASGI __call__
│   ├── module.py        # ModuleBase — orchestration, DI, ASGI aggregation
│   └── router.py        # RouterBase — HTTP routing, OpenAPI docs generation
├── decorators/          # Public decorator API
│   ├── service.py       # @service
│   ├── module.py        # @module
│   ├── router.py        # @router, @get, @post, @put, @delete, @patch
│   ├── config.py        # @config
│   └── lifecycle.py     # @after_config, @after_init, @before_startup, @before_shutdown
└── engine/              # Runtime engine
    ├── registry.py      # Service registry (O(1) lookup, parent chaining)
    ├── injector.py      # Topological sort (Kahn's algorithm)
    ├── hooks.py         # Lifecycle hook discovery
    ├── openapi.py       # OpenAPI 3.0.3 schema generation
    ├── params.py        # Route parameter resolution
    └── logging.py       # Framework logging
```

## Design Principles

1. **Decorator-driven** — Code is configuration; decorators transform plain classes
2. **Async-first** — Built on async/await, ASGI/Starlette
3. **Annotation-based DI** — Dependencies declared with type hints, resolved automatically
4. **Explicit inheritance** — Classes inherit from framework base classes (ServiceBase, ModuleBase, RouterBase)
5. **Automatic naming** — `ClassName` + suffix (`Service`, `Module`, `Router`)
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
