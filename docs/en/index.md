# Canary Framework

Canary Framework is a lightweight, decorator-driven Python async service framework designed for building modular, maintainable, and testable applications.

## Key Features

- **Decorator-driven**: Use simple decorators to define services, modules, and routes
- **Dependency injection**: Built-in DI container with automatic dependency resolution
- **Lifecycle management**: Complete lifecycle hooks for services and modules
- **ASGI compatible**: Built on Starlette for high-performance async web applications
- **Modular architecture**: Compose your application from reusable modules

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

## Next Steps

- [Quickstart](./quickstart.md) - A more comprehensive guide
- [Services](./services.md) - Learn about service definition and lifecycle
- [Modules](./modules.md) - Understand module composition
- [Web Routing](./web.md) - Build web APIs with routing
- [Dependency Injection](./dependency-injection.md) - Master the DI system
- [Lifecycle](./lifecycle.md) - Control service initialization and cleanup
- [Core Concepts](./core.md) - Dive into the framework internals
- [API Reference](./api-reference.md) - Complete API documentation
