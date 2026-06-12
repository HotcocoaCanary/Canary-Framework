# Quickstart

This guide will walk you through building a complete application with Canary Framework.

## 1. Prerequisites

First, ensure you have Python 3.12+ and pip installed:

```bash
python --version  # Should show Python 3.12+
pip --version     # Should show pip is installed
```

Install Canary Framework:

```bash
pip install canary-framework
```

## 2. Project Structure

Let's create a simple blog application:

```
my_blog/
├── main.py
└── services/
    ├── __init__.py
    ├── database.py
    ├── auth.py
    └── posts.py
```

## 3. Database Service

First, let's create a database service:

```python
# services/database.py
from canary_framework import service, after_init, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    def __init__(self):
        self.connection = None

    @after_init
    async def connect(self):
        self.connection = "connected"
        print("Database connected")

    @before_shutdown
    async def disconnect(self):
        self.connection = None
        print("Database disconnected")

    async def query(self, sql):
        return f"Executed: {sql}"
```

- `@service()` automatically names this service `DatabaseService`
- Lifecycle hooks `@after_init` and `@before_shutdown` manage connection setup and teardown

## 4. Auth Service

Now, let's create an auth service that depends on the database:

```python
# services/auth.py
from canary_framework import service, after_init
from canary_framework.core.service import ServiceBase
from .database import Database

@service()
class Auth(ServiceBase):
    db: Database  # Declare dependency via annotation

    def __init__(self):
        self.users = {}

    @after_init
    async def init_default_users(self):
        self.users = {
            "admin": {"name": "Admin", "role": "admin"},
            "user": {"name": "User", "role": "user"}
        }

    async def verify_user(self, username):
        return username in self.users

    async def get_user(self, username):
        return self.users.get(username)
```

- `db: Database` declares a dependency on `Database` — the framework automatically resolves and injects it
- The injected dependency is accessible as `self.db` (using the annotation key name)

## 5. Posts Router

Let's build a web router for our blog posts:

```python
# services/posts.py
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router
from pydantic import BaseModel, Field
from .auth import Auth
from .database import Database

class PostCreate(BaseModel):
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")

class PostResponse(BaseModel):
    id: int = Field(description="Post ID")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")

@service()
class Posts(ServiceBase):
    router = Router(prefix="/api/posts", tags=["Posts"])

    db: Database  # Auto-injected
    auth: Auth    # Auto-injected

    def __init__(self):
        self.posts = [
            {"id": 1, "title": "First Post", "content": "Hello World!", "author": "admin"}
        ]

    @router.get("/", summary="List posts", description="Get all blog posts")
    async def list_posts(self):
        return {"posts": self.posts}

    @router.get("/{post_id}",
                summary="Get post",
                description="Get post details by ID",
                response_model=PostResponse)
    async def get_post(self, post_id: int):
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            return post
        return {"error": "Post not found"}, 404

    @router.post("/",
                 summary="Create post",
                 description="Create a new blog post",
                 request_model=PostCreate,
                 response_model=PostResponse)
    async def create_post(self, body: PostCreate):
        new_post = {
            "id": len(self.posts) + 1,
            "title": body.title,
            "content": body.content,
            "author": body.author
        }
        self.posts.append(new_post)
        return new_post, 201

    @router.put("/{post_id}",
                summary="Update post",
                description="Update post content",
                request_model=PostCreate,
                response_model=PostResponse)
    async def update_post(self, post_id: int, body: PostCreate):
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            post.update({
                "title": body.title,
                "content": body.content,
                "author": body.author
            })
            return post
        return {"error": "Post not found"}, 404

    @router.delete("/{post_id}", summary="Delete post", description="Delete a post")
    async def delete_post(self, post_id: int):
        self.posts = [p for p in self.posts if p["id"] != post_id]
        return {"message": "Post deleted"}
```

- `router = Router(prefix="/api/posts", tags=["Posts"])` declares a `Router` class attribute with
  prefix and OpenAPI tags — method decorators live on this attribute
- `@router.get`, `@router.post`, `@router.put`, `@router.delete` replace standalone
  `@get` / `@post` / `@put` / `@delete` — the router instance carries route registrations
- Path parameters like `{post_id}` are auto-bound — declared as function parameters (`post_id: int`)
- `request_model` causes the body to be auto-parsed and passed as the `body` parameter
- Dependencies declared via annotations (`db: Database`, `auth: Auth`) are resolved automatically

## 6. Configuration

Create a configuration class using `@config` and `CanaryConfig`:

```python
# config.py
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    openapi_title: str = "My Blog API"
    log_level: str = "DEBUG"
```

## 7. Main Application Module

Now, let's compose everything into our main module:

```python
# main.py
from canary_framework import module
from canary_framework.core.module import ModuleBase
from services.database import Database
from services.auth import Auth
from services.posts import Posts

@module(services=[Database, Auth, Posts])
class BlogApp(ModuleBase):
    pass

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

- `@module(services=[...])` — auto-named `BlogAppModule`
- Module children are accessible as `app.Database`, `app.Auth`, `app.Posts` (class attribute names)

## 8. Run the Application

```bash
python main.py
```

Now you can test your API:

```bash
# List all posts
curl http://localhost:8000/api/posts/

# Get a single post
curl http://localhost:8000/api/posts/1

# Create a new post
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post", "content": "Another post!", "author": "user"}'

# Update a post
curl -X PUT http://localhost:8000/api/posts/2 \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post (Updated)", "content": "Updated content", "author": "user"}'

# Delete a post
curl -X DELETE http://localhost:8000/api/posts/2
```

## 9. Access OpenAPI Documentation

After starting the application, you can access these endpoints:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## What You've Learned

- How to define services with `@service()` — no manual names needed
- How to create routers with `Router` class attribute and `@router.get`/`@router.post` method decorators
- How to declare dependencies with Python type annotations (`db: Database`)
- How route parameters are auto-bound from path, query, and body
- How to compose everything into a module with `@module(services=[...])`
- How to use lifecycle hooks for initialization and cleanup
- How to use Pydantic models for request validation
- **Framework logging is auto-configured** — no `logging.basicConfig()` needed.
  Set `log_level` on your config object to control the verbosity (default: `"INFO"`)
## Next Steps

Explore the detailed documentation:
- [Configuration](./configuration.md)
- [Services](./services.md)
- [Modules](./modules.md)
- [Routers & HTTP](./web.md)
- [Dependency Injection](./dependency-injection.md)
- [Lifecycle](./lifecycle.md)
- [Architecture & Internals](./core.md)
- [API Reference](./api-reference.md)
