# API Reference

## Decorators

### `@service(name, *, deps=None)`

Declares a class as a Canary Framework service — the smallest runtime unit.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Globally unique service name |
| `deps` | `list[type] \| None` | no | Dependency classes, auto-injected as `self.<snake_case>` attributes |

```python
@service(name="db", deps=[CacheService])
class DBService:
    cache_service: CacheService
```

### `@module(name, *, deps=None, services=None)`

Declares a class as a composable module. Internally calls `@service` — modules are services too.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Globally unique module name |
| `deps` | `list[type] \| None` | no | Dependencies for the module itself |
| `services` | `list[type] \| None` | no | Child `@service`, `@module`, or `@router` classes |

```python
@module(name="App", deps=[MonitorService], services=[DBService, UserService])
class App:
    monitor_service: MonitorService
```

### Lifecycle Hooks

| Decorator | Signature | Execution Order | Description |
|-----------|-----------|-----------------|-------------|
| `@on_config` | `(self) -> None` | topological | Called after wiring and config field injection, during `Canary.config()` |
| `@on_init` | `(self) -> None` | topological | Called after `on_config`, during `Canary.init()` |
| `@on_start` | `(self) -> None` | topological | Called during `Canary.start()` |
| `@on_end` | `(self) -> None` | reverse | Called during `Canary.stop()` |

All hooks accept **only `self`** — dependencies and config are already instance attributes. Hooks can be sync (`def`) or async (`async def`).

### `LifecycleHook` Enum

```python
from canary_framework import LifecycleHook

LifecycleHook.CONFIG  # "on_config"
LifecycleHook.INIT    # "on_init"
LifecycleHook.START   # "on_start"
LifecycleHook.END     # "on_end"
```

### `@router(prefix="", *, name=None, deps=None, tags=None)`

Marks a class as an HTTP route handler. Internally calls `@service` — routers are services with full DI and lifecycle support.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prefix` | `str` | `""` | URL prefix for all routes in the group |
| `name` | `str \| None` | auto from class name | Service name |
| `deps` | `list[type] \| None` | `None` | Dependency classes |
| `tags` | `list[str] \| None` | `None` | OpenAPI tags applied as default |

### HTTP Method Decorators

```python
from canary_framework.web.fastapi import get, post, put, delete, patch

@get("/path", response_model=MyModel, status_code=200, tags=["items"])
async def handler(self) -> MyModel: ...

@post("/path", status_code=201)
async def create(self, body: CreateRequest) -> dict: ...
```

All HTTP method decorators accept the same optional keyword arguments: `response_model`, `status_code`, `summary`, `description`, `tags`, `dependencies`, `deprecated`, `response_description`.

---

## Engine Classes

### `Canary(target: type)`

Core engine — lifecycle orchestrator for the service graph.

| Attribute / Method | Description |
|--------------------|-------------|
| `.registry` | Global `Registry` (read-only after init) |
| `.startup_order` | Topologically sorted startup order (copy) |
| `await .config(config=Model())` | Collect → validate → sort → DI → config propagation → `on_config` |
| `await .init()` | Call `on_init` in topological order |
| `await .start()` | Call `on_start` in topological order |
| `await .stop()` | Call `on_end` in reverse topological order |

```python
app = Canary(MyRootModule)
await app.config(config=AppConfig())
await app.init()
await app.start()
# ... application runs ...
await app.stop()
```

### `WebCanary(target: type)`

Extends `Canary`, overrides `start()` for FastAPI + Uvicorn integration. Distributes root config model fields by prefix: `uvicorn_*` → uvicorn, `fastapi_*` → FastAPI(), no prefix → business config. Services access config via `self.config`.

```python
from pydantic import BaseModel
from canary_framework.web.fastapi import WebCanary

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

app = WebCanary(MyModule)
await app.config(config=AppConfig())
await app.init()
await app.start()      # blocks until server stops
```

---

## Exception Hierarchy

All framework exceptions inherit from `CanaryFrameworkError`:

```
CanaryFrameworkError
├── ConfigurationError
├── ServiceNotFoundError
├── CircularDependencyError
├── DependencyInjectionError
└── LifecycleHookError
```

| Exception | Triggered When |
|-----------|---------------|
| `CanaryFrameworkError` | Base class — catch to handle any framework error |
| `ConfigurationError` | Config construction fails (missing fields, validation errors) |
| `ServiceNotFoundError` | `Registry.get_by_name()` / `get_by_class()` lookup fails |
| `CircularDependencyError` | Topological sort detects a dependency cycle |
| `DependencyInjectionError` | `inject_deps()` encounters a `None` dependency instance |
| `LifecycleHookError` | An `on_config` / `on_init` / `on_start` / `on_end` hook raises an exception |

---

## Type System

### `ServiceMeta`

Metadata stored on `@service`-decorated classes. A frozen dataclass with `slots=True`:

- `name: str` — globally unique name
- `deps: list[type]` — dependency class list

### `ModuleMeta(ServiceMeta)`

Metadata stored on `@module`-decorated classes. Extends `ServiceMeta`:

- Inherits all fields from `ServiceMeta`
- `services: list[type]` — child service/module/router classes

### `RouterMeta(ServiceMeta)`

Metadata stored on `@router`-decorated classes. Extends `ServiceMeta`:

- Inherits all fields from `ServiceMeta`
- `prefix: str` — URL prefix for the route group
- `tags: list[str]` — OpenAPI tags

### Runtime Type Checks

```python
from canary_framework.core.decorators.service import get_service_meta, is_cf_service
from canary_framework.core.decorators.module import is_cf_module, get_module_meta
from canary_framework.web.fastapi.decorators.router import is_router, get_router_meta
from canary_framework.common._types import ServiceMeta, ModuleMeta, RouterMeta

meta = get_service_meta(SomeClass)
if isinstance(meta, RouterMeta):
    print(f"Router with prefix={meta.prefix}")
elif isinstance(meta, ModuleMeta):
    print(f"Module with {len(meta.services)} children")
```

```python
from canary_framework import Canary
from canary_framework.web.fastapi import router, get, delete, patch, post, put, WebCanary

__all__ = [
    # Core decorators
    "service",
    "module",
    # Lifecycle
    "on_config",
    "on_init",
    "on_start",
    "on_end",
    "LifecycleHook",
    # Engine
    "Canary",
    # Exceptions
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHookError",
    "ServiceNotFoundError",
    # Version
    "__version__",
]

# Web extras (via canary_framework.web.fastapi)
__all__ += ["WebCanary", "router", "get", "post", "put", "delete", "patch"]
```

---

## Internal Architecture

```
src/canary_framework/
├── __init__.py                 # public exports
├── common/
│   ├── __init__.py
│   ├── _types.py               # ServiceEntry, ServiceMeta, ModuleMeta, RouterMeta
│   ├── enums.py                # LifecycleHook (StrEnum)
│   ├── exceptions.py           # CanaryFrameworkError & subclasses
│   └── _logging.py             # structured logging, config sanitization
├── core/
│   ├── __init__.py
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── injector.py         # inject_deps() — setattr-based DI
│   │   ├── naming.py           # to_snake() — PascalCase → snake_case
│   │   └── sorter.py           # topological_sort() — Kahn BFS
│   ├── conductor/
│   │   ├── __init__.py
│   │   └── canary.py           # Canary engine — init/start/stop lifecycle
│   ├── container/
│   │   ├── __init__.py
│   │   └── registry.py         # Registry — O(1) lookup by name/class
│   └── decorators/
│       ├── __init__.py
│       ├── config.py           # @config — pydantic-settings wrapper
│       ├── lifecycle.py        # @on_init, @on_start, @on_end, find_hooks()
│       ├── module.py           # @module, is_cf_module(), get_module_meta()
│       ├── service.py          # @service, is_cf_service(), get_service_meta()

└── web/
    └── fastapi/
        ├── __init__.py         # WebCanary, router, get, post, put, delete, patch
        ├── conductor/
        │   ├── __init__.py
        │   └── web_canary.py   # WebCanary — FastAPI + Uvicorn integration
        └── decorators/
            ├── __init__.py
            └── router.py       # @router, @get, @post, @put, @delete, @patch
```

### Decorator Stack (Composition)

```
@module ── calls ──► @service           # modules are services + services list
@router ── calls ──► @service           # routers are services + prefix/tags

Each sets __cf_service__ = True, then upgrades __cf_service_meta__:
  @service → ServiceMeta
  @module  → ModuleMeta(ServiceMeta)
  @router  → RouterMeta(ServiceMeta)
```

### Initialization Flow

```
Canary.config(config=Model())
    │
    ├── _collect(target)           Phase 0: recursive discovery
    │   └── register in Registry   (idempotent — supports shared deps in DAG)
    │
    ├── _validate()                Phase 1: verify all deps references exist
    │
    ├── topological_sort()         Phase 2: Kahn BFS (O(V+E))
    │
    └── for each in startup_order:  Phase 3: wiring + on_config
        ├── inject_deps()           setattr dependencies → self.<snake_case>
        ├── inject_config()          setattr config fields from BaseModel → self.<field>
        └── on_config()              hook callback (self only, no arguments)

Canary.init()
    └── for each in startup_order:  on_init() (topological order)

Canary.start()
    └── for each in startup_order:  on_start() (topological order)

Canary.stop()
    └── for each in reversed:        on_end() (reverse topological order)
```
