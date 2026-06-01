<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">Lightweight Python Async Service Framework — Decorator-Driven, Zero Boilerplate</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/canary-framework/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img src="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework"><img src="https://img.shields.io/github/stars/HotcocoaCanary/Canary-Framework?style=social" alt="GitHub Stars"></a>
</p>

---

Canary Framework is a **decorator-driven** async service framework for Python. Core philosophy: **Services are the smallest unit, modules compose services, and modules themselves are services.**

## Core Features

- **Decorator-Driven** — Use `@service`, `@module`, `@router` decorators, zero inheritance required
- **Topological Startup** — Kahn's algorithm ensures dependencies start first
- **Dependency Injection** — `deps=[DBService]` auto-injected as `self.db_service`
- **Lifecycle Management** — `@after_config`/`@after_init`/`@before_startup`/`@before_shutdown` hooks
- **ASGI Compatible** — Built on Starlette, works with uvicorn and other ASGI servers
- **Modular Architecture** — Hierarchical composition with nested modules
- **OpenAPI Support** — Auto-generated Swagger UI and ReDoc documentation

## Design Principles

1. **Decorator-Driven** — Code is configuration, no complex setup required
2. **Async-First** — Built on async/await for high performance
3. **Explicit Dependencies** — Clear dependency declarations for better understanding and testing
4. **Convention Over Configuration** — Auto-injection, auto-mounting
5. **Composability** — Build complex systems through module composition

## Installation

```bash
pip install canary-framework
```

## Quick Start

```python
from canary_framework import module, service, router, get, post, after_config

@service(name="database")
class DatabaseService:
    def __init__(self):
        self.connection = None
    
    @after_config
    async def connect(self):
        self.connection = "connected"
        print("Database connected")

@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        return {"id": user_id, "name": "User"}

@router(name="api", prefix="/api", deps=[UserService])
class ApiRouter:
    @get("/users/{user_id}")
    async def get_user(self, request):
        user_id = request.path_params["user_id"]
        return await self.user_service.get_user(int(user_id))
    
    @post("/users")
    async def create_user(self, request):
        data = await request.json()
        return {"id": 1, **data}, 201

@module(name="app", services=[DatabaseService, UserService, ApiRouter])
class AppModule:
    pass

# Run with uvicorn
# uvicorn main:AppModule --host 0.0.0.0 --port 8000 --reload
```

## Web Example with OpenAPI

```python
from canary_framework import module, router, get, post
from pydantic import BaseModel, Field

class UserRequest(BaseModel):
    name: str = Field(description="User name")
    email: str = Field(description="User email")

class UserResponse(BaseModel):
    id: int = Field(description="User ID")
    name: str = Field(description="User name")
    email: str = Field(description="User email")

@router(name="users", prefix="/users", tags=["Users"])
class UsersRouter:
    @get("/", summary="List users", description="Get all users")
    async def list_users(self, request):
        return {"users": []}
    
    @post("/", 
          summary="Create user", 
          description="Create a new user",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, request, user: UserRequest):
        return {"id": 1, **user.model_dump()}, 201

@module(name="app", services=[UsersRouter])
class AppModule:
    pass
```

## OpenAPI Documentation

Access automatically generated documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Documentation

📖 Complete documentation: [Canary Framework Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

### Documentation Structure

- **Quickstart** — Build a complete application from scratch
- **Services** — Service definition, dependency injection, lifecycle
- **Modules** — Module composition, hierarchical structure
- **Web Routing** — Routing, HTTP methods, request handling
- **Dependency Injection** — DI system, topological sorting, registry
- **Lifecycle** — Lifecycle hooks, best practices
- **Core Concepts** — Design principles, architecture, internals
- **API Reference** — Complete API documentation

## Architecture

```
src/canary_framework/
├── common/              # Shared types, enums, exceptions
│   ├── errors.py        # Framework exceptions
│   ├── markers.py       # Metadata markers and accessors
│   └── types.py         # Data classes and type aliases
├── core/                # Core base classes
│   ├── module.py        # ModuleBase - module orchestration
│   ├── service.py       # ServiceBase - lifecycle management
│   └── router.py        # RouterBase - ASGI routing
├── decorators/         # Decorator implementations
│   ├── module.py        # @module decorator
│   ├── service.py       # @service decorator
│   ├── router.py        # @router, @get/@post/... decorators
│   └── lifecycle.py     # @after_config, @after_init, etc.
└── engine/             # Core engine components
    ├── registry.py      # Registry - service registration
    ├── injector.py      # Dependency injection, topological sort
    ├── hooks.py         # Lifecycle hook discovery
    ├── openapi.py       # OpenAPI schema generation
    ├── utils.py         # Helper utilities
    └── logging.py       # Logging utilities
```

### Lifecycle Flow

```
AppModule.configure()
  ├── Collect all services
  ├── Build dependency graph
  ├── Topological sort (Kahn's algorithm)
  ├── Instantiate services
  ├── Inject dependencies
  └── Call configure() + @after_config hooks on each service

AppModule.init()
  └── Call init() + @after_init hooks on each service

AppModule.startup()
  └── Call startup() + @before_startup hooks on each service

AppModule.shutdown()
  └── Call shutdown() + @before_shutdown hooks in reverse order
```

## Testing

```bash
# Run all tests
pytest

# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/
```

## Community

- 💬 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions)
- 🐛 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues)
- 📖 [Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[Apache 2.0](./LICENSE) · Copyright 2026 Zhang Wenbo (Canary)