<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">Lightweight Python Async Service Framework — Decorator-Driven, Annotation-Based DI</p>
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
- **Annotation-Based DI** — Declare dependencies with type annotations: `db: DatabaseService`, no boilerplate
- **Topological Startup** — Kahn's algorithm ensures dependencies start first
- **Lifecycle Management** — `@after_config`/`@after_init`/`@before_startup`/`@before_shutdown` hooks
- **ASGI Compatible** — Built on Starlette, works with uvicorn and other ASGI servers
- **Modular Architecture** — Hierarchical composition with nested modules
- **OpenAPI Support** — Auto-generated Swagger UI and ReDoc documentation

## Installation

```bash
pip install canary-framework
```

## Quick Start

```python
from canary_framework import module, service, router, get, post, after_config

@service()
class DatabaseService:
    @after_config
    async def connect(self):
        self.conn = "connected"

@service()
class UserService:
    db: DatabaseService

    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "Alice"}

@router(prefix="/api", tags=["users"])
class ApiRouter:
    user_service: UserService

    @get("/users/{user_id}")
    async def get_user(self, user_id: int) -> dict:
        return self.user_service.get_user(user_id)

    @post("/users")
    async def create_user(self, body: dict) -> dict:
        return {"id": 1, **body}

@module(services=[DatabaseService, UserService, ApiRouter])
class App:
    pass

# Run with uvicorn
# uvicorn main:App --host 0.0.0.0 --port 8000 --reload
```

## Web Example with OpenAPI

```python
from canary_framework import module, router, get, post
from pydantic import BaseModel, Field

class UserRequest(BaseModel):
    name: str = Field(description="User name")
    email: str = Field(description="User email")

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

@router(prefix="/users", tags=["Users"])
class UsersRouter:
    @get("/", summary="List users", description="Get all users")
    async def list_users(self) -> list[UserResponse]:
        return []

    @post("/",
          summary="Create user",
          description="Create a new user",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, user: UserRequest) -> UserResponse:
        return UserResponse(id=1, name=user.name, email=user.email)

@module(services=[UsersRouter])
class App:
    pass
```

## OpenAPI Documentation

Access automatically generated documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Architecture

```
src/canary_framework/
├── common/              # Shared infrastructure
│   ├── errors.py        # Framework exceptions
│   ├── markers.py       # Metadata markers, resolve_deps()
│   ├── routing.py       # Route path parsing
│   └── types.py         # Data classes and type aliases
├── core/                # Base classes
│   ├── module.py        # ModuleBase — orchestration and DI
│   ├── service.py       # ServiceBase — lifecycle management
│   └── router.py        # RouterBase — ASGI routing
├── decorators/          # Decorator implementations
│   ├── module.py        # @module
│   ├── service.py       # @service
│   ├── router.py        # @router, @get/@post/...
│   └── lifecycle.py     # @after_config, @after_init, etc.
└── engine/              # Runtime engine
    ├── registry.py      # Service registry
    ├── injector.py      # Topological sort
    ├── hooks.py         # Lifecycle hook discovery
    ├── openapi.py       # OpenAPI schema generation
    ├── utils.py         # make_subclass()
    └── logging.py       # Framework logging
```

### Dependency Injection Flow

```
@service() class MyService:
    db: DatabaseService      ←  1. User declares dependency via annotation

    ↓ configure phase

resolve_deps(MyService)
    → get_type_hints() reads {db: DatabaseService}
    → filters by CF_SERVICE_MARKER
    → returns {"db": DatabaseService}

    ↓ registration: recursively registers DatabaseService
    ↓ topological_sort: build dependency graph
    ↓ instantiation: creates instances in order
    ↓ wiring:

setattr(instance, "db", db_instance)   ←  3. Injected with annotation key name
```

### Lifecycle Flow

```
app.configure(config_instance)
  ├── Register all services + transitive deps
  ├── Topological sort (Kahn's algorithm)
  ├── Instantiate services
  ├── Inject dependencies (annotation-driven)
  ├── Call configure() on each service (topological order)
  └── Invoke @after_config hooks

app.init()
  ├── Invoke @after_init hook
  └── Call init() on each service (topological order)

app.startup()
  ├── Invoke @before_startup hook
  └── Call startup() on each service (topological order)

app.shutdown()
  ├── Invoke @before_shutdown hook
  └── Call shutdown() on each service (reverse topological order)
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
