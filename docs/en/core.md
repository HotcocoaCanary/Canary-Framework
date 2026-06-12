# Architecture & Internals

This document covers the internal design, data flow, and mechanics of Canary Framework.

## Design Overview

Canary Framework follows a three-layer architecture:

```
 common/  ──►  core/  ──►  decorators/  ──►  engine/
(types,        (ServiceBase,   (public API:      (registry,
 config,        ModuleBase,     @service,         dependencies,
 errors,        Router)         @module,          hooks,
 routing)                       @config,          openapi,
                                lifecycle         params,
                                hooks)            logging)
```

- **common/** — Zero framework-internal dependencies. Types, config model, error hierarchy, and route parsing that every other module imports.
- **core/** — The two base classes (`ServiceBase`, `ModuleBase`) and the `Router` class that provide lifecycle, DI wiring, route management, and ASGI integration.
- **decorators/** — The public API. Decorators validate base class inheritance, attach metadata markers, and auto-generate names.
- **engine/** — Runtime machinery: registry, topological sort, hook discovery, OpenAPI generation, parameter resolution, and logging.

## ServiceBase Internals

`ServiceBase` (core/service/_base.py) is the root base class for all framework components. ModuleBase inherits from it. The `Router` class is a standalone route manager used as a class attribute on services.

### `__init__`

```python
def __init__(self):
    self._cf_hooks: HookDict | None = None     # Lazily discovered hooks
    self._cf_parent_registry: object | None = None  # Injected by parent module
```

### Lifecycle Methods

| Method | Signature | What it does |
|---|---|---|
| `init()` | `() → None` | Invokes `AFTER_INIT` hook. |
| `startup()` | `() → None` | Invokes `BEFORE_STARTUP` hook. |
| `shutdown()` | `() → None` | Invokes `BEFORE_SHUTDOWN` hook. |

### `__call__` — ASGI 3 Interface

```python
async def __call__(self, scope, receive, send):
    if scope["type"] == "lifespan":
        await self._handle_lifespan(receive, send)
    else:
        asgi = getattr(self, "asgi_app", None)
        if asgi is not None:
            await asgi(scope, receive, send)
```

Maps ASGI lifespan events to `startup()`/`shutdown()`. Non-lifespan requests are delegated to `self.asgi_app` if available (set by subclasses).

### `_handle_lifespan`

Implements the ASGI lifespan protocol:

1. Receives `lifespan.startup` → calls `self.startup()` → sends `lifespan.startup.complete`
2. Receives `lifespan.shutdown` → calls `self.shutdown()` → sends `lifespan.shutdown.complete` → exits

### `_invoke_hook`

Lazy hook discovery via `find_hooks()` (engine/hooks.py). On first invocation, `find_hooks()` traverses the class MRO looking for methods marked with hook markers (`__cf_after_init__`, `__cf_before_startup__`, `__cf_before_shutdown__`) and binds them to the instance. Supports both sync and async hooks. Any exception raised by a hook is wrapped in `LifecycleHookError`.

## ModuleBase Internals

`ModuleBase` (core/module.py) extends `ServiceBase` and orchestrates child services.

### `init()` Flow

```
register services recursively
    ↓
topological_sort (Kahn's algorithm)
    ↓
instantiate services in order
    ↓
DI wiring: resolve_deps → setattr injection
    ↓
set _cf_parent_registry on all ServiceBase children
    ↓
init each child in order
    ↓
invoke AFTER_INIT hook
```

**Step-by-step:**

1. **Registration** (`_register_entry_with_deps`): For each service in the module's `services` list, register it in the registry. For each registered service, call `resolve_deps(cls)` to discover annotation-declared dependencies and register them recursively.

2. **Topological sort** (`topological_sort`): Uses Kahn's algorithm. Builds a dependency graph from `resolve_deps()` output, computes in-degrees, and produces a valid startup order. Detects circular dependencies.

3. **Instantiation**: Creates instances of all registered classes in topological order via `entry.cls()`.

4. **DI wiring**: For each instance, `resolve_deps(type(inst))` returns `{attr_name: dep_type}`. For each dependency, `setattr(inst, attr_name, registry.get_by_class(dep_type).instance)` injects the resolved instance. The annotation key name becomes the attribute name.

5. **Parent registry injection**: `inst._cf_parent_registry = registry` is set on every `ServiceBase` instance. This is how Routers access sibling RouterMetas and how Agents will access the registry.

6. **Child init**: Each child's `init()` is called in topological order. Config is auto-discovered from `services` list — any class passing `issubclass(CanaryConfig)` is treated as the configuration.

### `asgi_app` Property

Lazily builds a Starlette `Router` by iterating over child services in startup order:

- **Duck-typing mounts**: If `hasattr(inst, "asgi_app")`, the child is mounted at its `get_mount_path()` (or `f"/{name}"` fallback) via Starlette `Mount`.
- **Root routes**: If `hasattr(inst, "_cf_get_root_routes")`, the child's root route list is contributed to the module-level router. This is how Routers provide `/docs`, `/redoc`, `/openapi.json` at the root level.

Mount path collisions are detected and raise `ValueError`.

### Lifecycle Propagation

All lifecycle methods (init, startup, shutdown) propagate to children:
- **Forward order** (topological): init, startup
- **Reverse order**: shutdown

## Router Internals

`Router` (core/router/_base.py) is a standalone route manager, not a `ServiceBase` subclass. It is used as a class attribute on `@service()` or `@module()` decorated classes.

### Constructor

```python
Router(prefix: str = "", *, tags: list[str] | None = None)
```

- `prefix` — URL prefix applied to all routes in this router (e.g., `"/api"`)
- `tags` — OpenAPI tags auto-applied to all endpoints in this router

Internally stores `self._route_infos: list[RouteInfo]` as routes are registered via the method decorators.

### HTTP Method Decorators

Each `Router` instance provides method decorators (`@router.get`, `@router.post`, `@router.put`, `@router.delete`, `@router.patch`) that register `RouteInfo` objects internally:

1. Parses the path via `parse_route_path(path)` → splits into `starlette_path`, `path_params`, `query_params`
2. Resolves handler parameter types via `resolve_params(fn)`
3. Auto-detects `request_model` from handler annotations
4. Constructs a `RouteInfo` dataclass with all metadata
5. Appends to `self._route_infos`

The decorator returns the original function unchanged (no wrapping).

### Route Collection

`_collect_routes()` is a free function that works on any object instance:

1. Reads `getattr(instance, "router", None)` — if it's a `Router`, iterates `router._route_infos`
2. For each `RouteInfo`, calls `_route_handler()` to create a Starlette `Route`

### `_route_handler`

1. Reads route metadata from `RouteInfo`
2. Creates an `endpoint` closure that:
   - Binds path params from `request.path_params` with type conversion
   - Binds query params from `request.query_params` with type conversion
   - If `request_model` is set, calls `await request.json()` and parses with Pydantic
   - Calls `await handler(...)` with resolved kwargs
   - Converts return value via `_auto_response()`
3. Returns `Route(starlette_path, endpoint=endpoint, methods=[method])`

### OpenAPI Documentation

The first service with a `Router` in a module generates documentation on `startup()`:

1. Collects `RouteInfo` from self and all sibling services via `_cf_parent_registry`
2. Calls `generate_openapi_schema()` with all route infos and config values
3. Generates Swagger UI and ReDoc HTML pages
4. Creates root routes for `/docs`, `/redoc`, `/openapi.json`
5. First-wins registration: only the first router in a module registers docs

### Mount Path

Services with a `Router` are mounted at `router.prefix` if set (e.g., `"/api"`), otherwise at `f"/{service_name}"`.

## Dependency Injection Flow

```
resolve_deps(cls) → __annotations__ → filter by CF_SERVICE_MARKER
    ↓
{attr_name: dep_type}
    ↓
recursive registration → topological_sort (Kahn)
    ↓
startup_order: [name1, name2, ...]
    ↓
instantiation → setattr injection → lifecycle
```

### `resolve_deps(cls)`

Reads `cls.__annotations__` via `typing.get_type_hints()` and returns only those entries whose type has `CF_SERVICE_MARKER` set (i.e., is a `@service` or `@module` decorated class):

```python
# For class:
@service()
class Auth(ServiceBase):
    db: Database   # ✓ CF_SERVICE_MARKER — included
    x: int         # ✗ Not a service — excluded

# resolve_deps(Auth) → {"db": Database}
```

### `topological_sort(registry)`

Uses Kahn's algorithm:

1. Build adjacency list from `resolve_deps()`
2. Compute in-degree for each node
3. Queue nodes with in-degree 0
4. Process queue, decrementing in-degrees
5. If not all nodes are processed → `CircularDependencyError`

## Metadata System

Decorators set metadata markers on classes. These markers drive all framework behavior.

### Markers

| Constant | Value | Purpose |
|---|---|---|
| `CF_SERVICE_MARKER` | `"__cf_service__"` | Set to `True` on all `@service` and `@module` classes |
| `CF_SERVICE_META` | `"__cf_service_meta__"` | Stores `ServiceMeta` / `ModuleMeta` / `RouterMeta` instance |
| `CF_NAME_ATTR` | `"__cf_name__"` | Auto-generated name (e.g., `"DatabaseService"`) |
| `ROUTE_ATTR` | `"__cf_route__"` | Route metadata dict on HTTP handler methods |
| `CF_CONFIG_MARKER` | `"__cf_config__"` | Set to `True` on `@config` classes |

### Meta Types

- **`ServiceMeta(name)`** — Set by `@service`
- **`ModuleMeta(name, services)`** — Set by `@module`, extends `ServiceMeta`
- **`RouterMeta(name, prefix, tags, routes)`** — Set by the `Router` class, extends `ServiceMeta`

### Type Checks

`is_cf_service`, `is_cf_module`, and `is_cf_router` use `isinstance` checks against the meta type stored in `CF_SERVICE_META`:

```python
def is_cf_service(cls):  # hasattr(cls, CF_SERVICE_MARKER)
def is_cf_module(cls):   # isinstance(getattr(cls, CF_SERVICE_META, None), ModuleMeta)
def is_cf_router(cls):   # isinstance(getattr(cls, CF_SERVICE_META, None), RouterMeta)
```

## ASGI Integration

1. **`ServiceBase.__call__`** — Handles ASGI lifespan protocol (startup/shutdown events). Delegates non-lifespan requests to `asgi_app`.

2. **`ModuleBase.asgi_app`** — Aggregates child ASGI apps via duck-typing. Mounts children with `asgi_app` at their mount paths. Contributes root routes from children with `_cf_get_root_routes()`.

3. **`Router.asgi_app`** — The first service with a `Router` attribute builds a Starlette `Router` from collected route handlers (via `_collect_routes()`). On `startup()`, generates OpenAPI schema and registers documentation endpoints as root routes (first-wins).

## Error Handling

```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError            # Config load/validation failure
    ├── ServiceNotFoundError          # Service lookup failure
    ├── CircularDependencyError       # Topological sort cycle detected
    ├── DependencyInjectionError      # DI wiring failure (None instance, etc.)
    └── LifecycleHookError            # Hook raised unhandled exception
```

All framework errors inherit from `CanaryFrameworkError`, so callers can catch a single type for all framework errors.
