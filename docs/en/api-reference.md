# API Reference

## Decorators

### `@service(name, *, config=None, deps=None)`

Declares a class as a CF framework service (smallest runtime unit).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | ✓ | Globally unique name, used for dependency declarations and name indexing |
| `config` | `type \| None` | | `@config`-decorated config class; when None, inherits from parent module |
| `deps` | `list[type] \| None` | | Dependency service class list, auto-injected as snake_case attributes |

### `@module(name, *, config=None, services=None)`

Declares a class as a CF framework module (container composing services). Modules are themselves services.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | ✓ | Globally unique name |
| `config` | `type \| None` | | Module config class (inherited by child services when not declared) |
| `services` | `list[type] \| None` | | Child service and sub-module class list |

### `@config`

Converts a plain class into a pydantic-settings `BaseSettings` subclass. Built-in `env_file=".env"`.

Priority: **environment variable > .env file > default value**.

```python
@config
class MyConfig:
    key: str = "default"
```

### Lifecycle Hooks

| Decorator | Signature | Execution Order | Description |
|-----------|-----------|-----------------|-------------|
| `@on_init` | `(ctx: Context)` | Topological | Dependencies injected, config loaded |
| `@on_start` | `()` | Topological | No arguments |
| `@on_end` | `()` | Reverse | No arguments |

Hook methods can be `sync` or `async` — the framework automatically adapts via `asyncio.iscoroutine`.

### `LifecycleHook` Enum

```python
from canary_framework import LifecycleHook

LifecycleHook.INIT   # "on_init"
LifecycleHook.START  # "on_start"
LifecycleHook.END    # "on_end"
```

---

## Engine Classes

### `Canary(target: type)`

Core engine, lifecycle orchestrator.

| Attribute/Method | Description |
|------------------|-------------|
| `.registry` | Global `Registry` |
| `.startup_order` | Topologically sorted startup order list |
| `await .init()` | Collect → validate → topological sort → context tree → DI → config loading → on_init |
| `await .start()` | Call on_start in topological order |
| `await .stop()` | Call on_end in reverse order |

### `WebCanary(target: type)`

Extends Canary, overrides only `start()` for FastAPI + Uvicorn integration.

Distributes params from root module `@config` by prefix: `uvicorn_*` → uvicorn, `fastapi_*` → FastAPI(), no prefix → business config.

```python
@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

app = WebCanary(MyModule)
await app.init()
await app.start()
```

### `Context`

Unified runtime context. Delegates config lookup and dependency resolution upward through the parent chain.

| Method | Return Type | Description |
|--------|-------------|-------------|
| `.get_config(type[T])` | `T` | **Type-safe** config access, looked up via parent chain |
| `.get_service(type[T])` | `T` | **Type-safe** service instance access |

---

## Exception Hierarchy

All framework exceptions inherit from `CanaryFrameworkError`, allowing unified catching:

```python
from canary_framework import (
    CanaryFrameworkError,      # base class
    ConfigurationError,         # config loading/lookup failure
    ServiceNotFoundError,       # service/module not registered
    CircularDependencyError,    # circular dependency
    DependencyInjectionError,   # dependency injection failure
    LifecycleHookError,         # lifecycle hook exception
)
```

| Exception | Triggered When |
|-----------|---------------|
| `ConfigurationError` | `ctx.get_config()` cannot find a config instance |
| `ServiceNotFoundError` | `Registry.get_by_name/class()` or `ctx.get_service()` not found |
| `CircularDependencyError` | Topological sort detects a cycle |
| `DependencyInjectionError` | `inject_deps()` encounters a None dependency instance |
| `LifecycleHookError` | `on_init/start/end` hook raises an exception |

---

## Internal Architecture

```
src/canary_framework/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── _types.py            # ServiceEntry, ServiceMeta, ModuleMeta
│   ├── enums.py             # LifecycleHook
│   └── exceptions.py        # CanaryFrameworkError & subclasses
├── core/
│   ├── __init__.py
│   ├── decorators/
│   │   ├── __init__.py
│   │   ├── config.py        # @config (built-in env_file=".env")
│   │   ├── lifecycle.py     # @on_init, @on_start, @on_end
│   │   ├── module.py        # @module
│   │   └── service.py       # @service
│   ├── conductor/
│   │   ├── __init__.py
│   │   ├── canary.py        # Canary engine
│   │   └── context.py       # Context
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── injector.py      # dependency injection
│   │   ├── sorter.py        # topological sort
│   │   └── naming.py        # naming utilities
│   └── container/
│       ├── __init__.py
│       └── registry.py      # service registry
└── web/
    └── fastapi/
        ├── __init__.py
        ├── conductor/
        │   ├── __init__.py
        │   └── web_canary.py # WebCanary engine
        └── decorators/
            ├── __init__.py
            ├── router.py    # @router, @get, @post, ...
            └── web.py       # @web
```

## Initialization Flow

```
Canary.init()
    │
    ├── _collect(target)         Phase 0: recursively collect @service/@module classes
    │   ├── register in Registry
    │   ├── record parent_entry
    │   └── config_cls inheritance
    │
    ├── _validate()              Phase 1: validate dependency integrity
    │
    ├── topological_sort()       Phase 2: Kahn topological sort (O(V+E))
    │
    ├── _build_context_tree()    Phase 3: build Context parent chain by module tree
    │
    └── for each in startup_order:   Phase 4: init in topological order
        ├── inject_deps()            setattr inject dependencies
        ├── config_cls()             direct instantiation (pydantic-settings auto-reads .env)
        └── on_init(entry.context)   hook callback
```
