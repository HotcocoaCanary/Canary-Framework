# API Reference

## Decorators

### `@service(name, *, config=None, deps=None)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | ✓ | Globally unique name |
| `config` | `type \| None` | | @config-decorated config class |
| `deps` | `list[type] \| None` | | Dependency service class list |

### `@module(name, *, config=None, services=None)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | ✓ | Globally unique name |
| `config` | `type \| None` | | Module config class (inheritable by child services) |
| `services` | `list[type] \| None` | | Child service and module class list |

### `@config`

Converts a plain class into a pydantic-settings `BaseSettings` subclass. Built-in `env_file=".env"`. Priority: **env vars > .env file > defaults**.

```python
@config
class MyConfig:
    key: str = "default"
```

### `@on_init` / `@on_start` / `@on_end`

Lifecycle hook decorators. All optional. Hook methods can be `sync` or `async`.

---

## Engine Classes

### `Canary(target: type)`

Core engine, lifecycle orchestrator.

```python
app = Canary(MyModule)
await app.init()    # collect → validate → sort → context tree → DI → config → on_init
await app.start()   # call on_start in topological order
await app.stop()    # call on_end in reverse order
```

### `WebCanary(target: type)`

Extends Canary, overrides `start()` for FastAPI + Uvicorn. Routes root module @config by prefix: `uvicorn_*` → uvicorn, `fastapi_*` → FastAPI().

```python
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"
    fastapi_version: str = "1.0.0"

app = WebCanary(MyModule)
await app.init()
await app.start()
```

### `Context(entry, parent, registry)`

Unified runtime context. Delegates upward through parent chain.

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `.config` | `object` | Config instance, looked up via parent chain if not found |
| `.service` | `object` | Service/module instance bound to this context |
| `.resolve(cls)` | `object` | Look up a registered service via parent chain |

---

## Internal Architecture

```
canary_framework/
├── core/
│   ├── decorators/          # User-facing decorators
│   │   ├── config.py        # @config (built-in env_file=".env")
│   │   ├── service.py       # @service
│   │   ├── module.py        # @module
│   │   └── lifecycle.py     # @on_init, @on_start, @on_end
│   ├── engine/
│   │   ├── canary.py        # Canary engine (orchestration + context tree)
│   │   ├── context.py       # Context (unified context, parent chain lookup)
│   │   ├── injector.py      # Dependency injection
│   │   └── sorter.py        # Topological sort
│   ├── registry/
│   │   └── registry.py      # Registry (ServiceEntry + Registry)
│   └── utils/
│       └── naming.py        # Naming utility (CamelCase → snake_case)
│
└── web/
    └── fastapi/
        ├── web_canary.py    # WebCanary engine (extends Canary)
        └── decorators/
            ├── web.py       # @web
            └── router.py    # @router, @get, @post, ...
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
    ├── topological_sort()       Phase 2: Kahn topological sort
    │
    ├── _build_context_tree()    Phase 3: build Context parent chain by module tree
    │
    └── for each in startup_order:   Phase 4: init in topological order
        ├── inject_deps()            setattr inject dependencies
        ├── config_cls()             instantiate config (pydantic-settings auto-reads .env)
        └── on_init(entry.context)   hook callback
```
