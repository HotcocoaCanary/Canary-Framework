# Canary Framework

Canary Framework is a lightweight, decorator-driven Python async service framework designed for building modular, maintainable, and testable applications.

## Key Features

- **Decorator-driven**: Use simple decorators to define services, modules, and routes
- **Dependency injection**: Built-in DI container with automatic dependency resolution
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

@router(name="api")
class ApiRouter:
    @get("/hello")
    async def hello(self, request):
        return {"message": "Hello, Canary!"}
    
    @post("/echo")
    async def echo(self, request):
        data = await request.json()
        return {"echo": data}

@module(name="app", services=[ApiRouter])
class AppModule:
    pass

# Run with uvicorn
# uvicorn main:AppModule --reload
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

@service(name="database")
class DatabaseService:
    @after_config
    async def connect(self):
        print("Database connected")
```

### Module

Modules are containers that organize and compose services:

```python
from canary_framework import module

@module(name="app", services=[DatabaseService, ApiRouter])
class AppModule:
    pass
```

### Router

Routers handle HTTP requests:

```python
from canary_framework import router, get

@router(name="users", prefix="/users")
class UsersRouter:
    @get("/")
    async def list_users(self, request):
        return {"users": []}
```

### Dependency Injection

Services can declare dependencies, which the framework automatically injects:

```python
@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        return await self.database_service.query(...)
```

## Next Steps

- [Quickstart](./quickstart.md) - A more comprehensive guide
- [Services](./services.md) - Learn about service definition and lifecycle
- [Modules](./modules.md) - Understand module composition
- [Web Routing](./web.md) - Build web APIs with routing
- [Dependency Injection](./dependency-injection.md) - Master the DI system
- [Lifecycle](./lifecycle.md) - Control service initialization and cleanup
- [Core Concepts](./core.md) - Dive into the framework internals
- [API Reference](./api-reference.md) - Complete API documentation

## Design Principles

1. **Decorator-driven** - Code is configuration
2. **Async-first** - Built on async/await
3. **Explicit dependencies** - Clear dependency declarations
4. **Convention over configuration** - Sensible defaults
5. **Composability** - Build complex systems through modules