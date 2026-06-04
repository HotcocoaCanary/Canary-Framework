# Canary Framework

Canary Framework is a lightweight, decorator-driven Python async service framework designed for building modular, maintainable, and testable applications.

## Key Features

- **Decorator-driven**: Simple decorators define services, modules, and routes — no boilerplate
- **Annotation-based DI**: Declare dependencies with Python type annotations — no `deps` lists
- **Automatic naming**: Service, module, and router names are derived from class names
- **Lifecycle management**: Complete lifecycle hooks for services and modules
- **ASGI compatible**: Built on Starlette for high-performance async web applications
- **Modular architecture**: Compose your application from reusable modules
- **OpenAPI support**: Auto-generated Swagger UI and ReDoc documentation

## Installation

```bash
pip install canary-framework
```

## Quick Start

Here's a minimal example to get you started:

```python
from canary_framework import module, router, get, post

@router(prefix="")
class Api:
    @get("/hello")
    async def hello(self):
        return {"message": "Hello, Canary!"}

    @post("/echo")
    async def echo(self, body: dict):
        return {"echo": body}

@module(services=[Api])
class App:
    pass

# Run with uvicorn
# uvicorn main:App --reload
```

## OpenAPI Documentation

After starting the application, you can access these endpoints:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Core Concepts

### Service

Services are the building blocks of your application, encapsulating business logic:

```python
from canary_framework import service, after_config

@service()
class Database:
    @after_config
    async def connect(self):
        print("Database connected")
```

### Module

Modules are containers that organize and compose services:

```python
from canary_framework import module

@module(services=[Database, Api])
class App:
    pass
```

### Router

Routers handle HTTP requests with auto-bound parameters:

```python
from canary_framework import router, get

@router(prefix="/users")
class Users:
    @get("/")
    async def list_users(self):
        return {"users": []}
```

### Dependency Injection

Declare dependencies with type annotations — the framework automatically resolves and injects them:

```python
@service()
class UserRepo:
    db: Database  # Auto-injected by the framework

    async def get_user(self, user_id):
        return await self.db.query(...)
```

## Next Steps

- [Quickstart](./quickstart.md) - A more comprehensive guide
- [Services](./services.md) - Learn about service definition and lifecycle
- [Modules](./modules.md) - Understand module composition
- [Web Routing](./web.md) - Build web APIs with routing
- [Dependency Injection](./dependency-injection.md) - Master the annotation-based DI system
- [Lifecycle](./lifecycle.md) - Control service initialization and cleanup
- [Core Concepts](./core.md) - Dive into the framework internals
- [API Reference](./api-reference.md) - Complete API documentation

## Design Principles

1. **Decorator-driven** — Code is configuration
2. **Async-first** — Built on async/await
3. **Annotation-based DI** — Dependencies declared with type hints
4. **Automatic naming** — Names derived from class names, no manual strings
5. **Composability** — Build complex systems through modules
