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

- **Decorator-Driven** — Use `@service` and `@module` decorators with explicit base class inheritance
- **Annotation-Based DI** — Declare dependencies with type annotations: `db: DatabaseService`, no boilerplate
- **Topological Startup** — Kahn's algorithm ensures dependencies start first
- **Lifecycle Management** — `@before_startup` / `@before_shutdown` hooks
- **ASGI Compatible** — Built on Starlette, works with uvicorn and other ASGI servers
- **Modular Architecture** — Hierarchical composition with nested modules
- **OpenAPI Support** — Auto-generated Swagger UI and ReDoc documentation

## Installation

```bash
pip install canary-framework
```

## Quick Start

```python
from canary_framework import service, module
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router

@service()
class Database(ServiceBase):
    async def init(self):
        await super().init()
        self.conn = "connected"

@service()
class UserService(ServiceBase):
    db: Database

    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "Alice"}

@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["users"])
    user_service: UserService

    @router.get("/users/{user_id}")
    async def get_user(self, user_id: int) -> dict:
        return self.user_service.get_user(user_id)

    @router.post("/users")
    async def create_user(self, body: dict) -> dict:
        return {"id": 1, **body}

@module(services=[Database, UserService, Api])
class App(ModuleBase):
    pass

# ---- Entry Point ----

async def setup():
    app = App()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn

    app = asyncio.run(setup())
    uvicorn.run(app, lifespan="on")
```

## Configuration

Use `@config` with `CanaryConfig` to customize framework behavior:

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    openapi_title: str = "My API"
    log_level: str = "DEBUG"

@module(services=[AppConfig, Database, Api])
class App(ModuleBase):
    config: AppConfig

async def setup():
    app = App()
    await app.init()
    return app, app.config
```

## Web Example with OpenAPI

```python
from canary_framework import module
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from pydantic import BaseModel, Field

class UserRequest(BaseModel):
    name: str = Field(description="User name")
    email: str = Field(description="User email")

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

@service()
class Users(ServiceBase):
    router = Router(prefix="/users", tags=["Users"])

    @router.get("/", summary="List users", description="Get all users")
    async def list_users(self) -> list[UserResponse]:
        return []

    @router.post("/",
          summary="Create user",
          description="Create a new user",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, body: UserRequest) -> UserResponse:
        return UserResponse(id=1, name=body.name, email=body.email)

@module(services=[Users])
class App(ModuleBase):
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
│   ├── config.py        # CanaryConfig
│   ├── errors.py        # Framework exceptions
│   ├── logging.py       # Framework logging
│   └── types.py         # Data classes, markers, and type aliases
├── core/                # Base classes
│   ├── module/
│   │   └── _base.py     # ModuleBase — orchestration and DI
│   ├── service/
│   │   ├── _base.py     # ServiceBase — lifecycle and ASGI
│   │   └── _hooks.py    # Lifecycle hook invocation
│   └── router/
│       ├── _base.py     # Router — route collection and ASGI routing
│       └── _utils.py    # Route handler building
├── decorators/          # Decorator implementations
│   ├── module.py        # @module
│   ├── service.py       # @service
│   ├── config.py        # @config
│   └── lifecycle.py     # @before_startup, @before_shutdown
└── engine/              # Runtime engine
    ├── registry.py      # Service registry
    ├── dependencies.py  # Topological sort + resolve_deps
    ├── openapi.py       # OpenAPI schema generation
    └── params.py        # Route parameter resolution
```

### Dependency Injection Flow

```
@service() class MyService:
    db: DatabaseService      ←  1. User declares dependency via annotation

resolve_deps(MyService)
    → get_type_hints() reads {db: DatabaseService}
    → filters by CF_SERVICE_MARKER
    → returns {"db": DatabaseService}

    ↓ topo sort: Kahn's algorithm builds dependency order
    ↓ instantiation: creates instances in order
    ↓ wiring:

setattr(instance, "db", db_instance)   ←  2. Injected with annotation key name
```

### Lifecycle Flow

```
app.init()
  ├── Register all services + transitive deps
  ├── Topological sort (Kahn's algorithm)
  ├── Instantiate services
  ├── Inject dependencies (annotation-driven)
  ├── Call init() on each service (topological order)

app.startup()
  ├── Invoke @before_startup hook
  └── Call startup() on each service (topological order)

app.shutdown()
  ├── Invoke @before_shutdown hook
  └── Call shutdown() on each service (reverse topological order)
```

## Examples

The [examples/](./examples/) directory contains runnable, tested examples:

| File | Description |
|---|---|
| `01_standalone.py` | Single service with Router, standalone mode |
| `02_module_compose.py` | Module composing multiple services |
| `03_nested_modules.py` | Nested module hierarchy |
| `04_module_router.py` | Module with its own Router |
| `05_config.py` | Configuration with @config() + CanaryConfig |
| `06_lifecycle.py` | Lifecycle hooks (before_startup, before_shutdown) |
| `07_validation.py` | Pydantic request/response validation |
| `08_parameters.py` | Path, query, body parameter binding |
| `09_openapi.py` | OpenAPI title/version/description customization |
| `10_full_app.py` | Complete blog API with nested modules |

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
