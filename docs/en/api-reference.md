# API Reference

Complete API documentation for Canary Framework.

## Main Exports

```python
from canary_framework import (
    # Decorators
    service, module, router,
    get, post, put, delete, patch,
    after_config, after_init, before_startup, before_shutdown,

    # Base Classes
    ServiceBase, ModuleBase, RouterBase,

    # Exceptions
    CanaryFrameworkError,
    DependencyInjectionError,
    CircularDependencyError,
    LifecycleHookError,
    ServiceNotFoundError,

    # Enums
    LifecycleHook,

    # Version
    __version__
)
```

---

## Decorators

### @service

Marks a class as a service.

**Signature:**
```python
def service() -> Callable[[type], type[ServiceBase]]
```

**Parameters:**
- None. The `name` and `deps` parameters have been removed.

The service name is auto-generated as `ClassName` + `"Service"`. Dependencies are declared via type annotations on the class body.

**Example:**
```python
@service()
class Database:
    pass
```

---

### @module

Marks a class as a module container.

**Signature:**
```python
def module(
    *,
    services: List[type] = None
) -> Callable[[type], type[ModuleBase]]
```

**Parameters:**
- `services` (List[type], keyword-only): Services, routers, and sub-modules this module contains

The `name` and `deps` parameters have been removed. The module name is auto-generated as `ClassName` + `"Module"`.

**Example:**
```python
@module(services=[Database, Auth, Api])
class App:
    pass
```

---

### @router

Marks a class as a router.

**Signature:**
```python
def router(
    prefix: str = "",
    *,
    tags: List[str] = None
) -> Callable[[type], type[RouterBase]]
```

**Parameters:**
- `prefix` (str, positional, default `""`): URL prefix for all routes
- `tags` (List[str], keyword-only): OpenAPI tags for documentation

The `name` and `deps` parameters have been removed. The router name is auto-generated as `ClassName` + `"Router"`. Dependencies are declared via type annotations.

**Example:**
```python
@router(prefix="/api", tags=["API"])
class Api:
    pass
```

---

### HTTP Method Decorators

Mark methods as route handlers.

**Signatures:**
```python
def get(path: str, **kwargs) -> Callable
def post(path: str, **kwargs) -> Callable
def put(path: str, **kwargs) -> Callable
def delete(path: str, **kwargs) -> Callable
def patch(path: str, **kwargs) -> Callable
```

**Parameters:**
- `path` (str, required): URL path for the route
- `summary` (str): Short summary for OpenAPI
- `description` (str): Detailed description for OpenAPI
- `request_model` (Pydantic BaseModel): Auto-parse request body into this model. Passed as `body` parameter.
- `response_model` (Pydantic BaseModel): Response data model for OpenAPI
- `responses` (dict): Custom response definitions
- `tags` (list[str]): OpenAPI tags
- `deprecated` (bool): Mark as deprecated
- `operation_id` (str): Unique operation identifier
- `path_params` (dict): Path parameter definitions for schema enrichment
- `query_params` (dict): Query parameter definitions for schema enrichment

Route handlers do **not** receive a `request` parameter. Path parameters, query parameters, and request body are auto-bound.

**Example:**
```python
@router(prefix="/users")
class Users:
    @get("/{user_id}")
    async def get_user(self, user_id: int):
        # user_id auto-bound from URL path
        pass

    @post("/", request_model=UserCreate)
    async def create_user(self, body: UserCreate):
        # body auto-parsed from request
        pass
```

---

### Lifecycle Hook Decorators

Mark methods as lifecycle hooks.

**Signatures:**
```python
def after_config(func) -> HookFunction
def after_init(func) -> HookFunction
def before_startup(func) -> HookFunction
def before_shutdown(func) -> HookFunction
```

**Example:**
```python
@service()
class Database:
    @after_config
    async def connect(self):
        pass

    @before_shutdown
    async def disconnect(self):
        pass
```

---

## Base Classes

### ServiceBase

Base class for services.

**Attributes:**
- `config`: Configuration object (set during configure phase)
- `_cf_hooks`: Internal hook registry

**Methods:**
- `async configure(config_instance=None)`: Configure the service
- `async init()`: Initialize the service
- `async startup()`: Start the service
- `async shutdown()`: Shutdown the service
- `async _invoke_hook(hook)`: Invoke a lifecycle hook

---

### ModuleBase

Base class for modules, extends ServiceBase.

**Attributes:**
- `config`: Configuration object
- `_cf_parent_registry`: Parent registry (if any)
- `_cf_registry`: Service registry
- `_cf_startup_order`: Sorted startup order
- `_cf_asgi_app`: Cached ASGI app

**Properties:**
- `asgi_app`: Starlette router with mounted child services

**Methods:**
- `async configure(config_instance=None)`: Configure module and all services
- `async init()`: Initialize module and all services
- `async startup()`: Start module and all services
- `async shutdown()`: Shutdown module and all services
- `async __call__(scope, receive, send)`: ASGI app interface
- `async _handle_lifespan(receive, send)`: Handle ASGI lifespan events
- `_register_entry_with_deps(cls, registry)`: Recursively register services with annotation-resolved deps

---

### RouterBase

Base class for routers, extends ServiceBase.

**Properties:**
- `asgi_app`: Starlette router with collected routes

**Methods:**
- `async __call__(scope, receive, send)`: ASGI app interface

---

## Enums

### LifecycleHook

Lifecycle hook phases.

**Values:**
- `LifecycleHook.AFTER_CONFIG`: "after_config"
- `LifecycleHook.AFTER_INIT`: "after_init"
- `LifecycleHook.BEFORE_STARTUP`: "before_startup"
- `LifecycleHook.BEFORE_SHUTDOWN`: "before_shutdown"

---

## Exceptions

### CanaryFrameworkError

Base exception for all framework errors.

**Hierarchy:**
```
Exception
└── CanaryFrameworkError
    ├── DependencyInjectionError
    ├── CircularDependencyError
    ├── LifecycleHookError
    ├── ConfigurationError
    └── ServiceNotFoundError
```

---

### DependencyInjectionError

Error during dependency injection.

---

### CircularDependencyError

Circular dependency detected.

---

### LifecycleHookError

Error in a lifecycle hook.

---

### ServiceNotFoundError

Service not found in registry.

---

### ConfigurationError

Configuration error.

---

## Common Module

### Markers

Constants and helpers for identifying framework classes.

**Constants:**
- `CF_SERVICE_MARKER`: `"__cf_service__"`
- `CF_MODULE_MARKER`: `"__cf_module__"`
- `CF_ROUTER_MARKER`: `"__cf_router__"`
- `CF_NAME_ATTR`: `"__cf_name__"`
- `ROUTE_ATTR`: `"__cf_route__"`
- `CF_HOOK_MARKER_MAP`: Mapping of LifecycleHook to marker strings

**Functions:**
- `is_cf_service(cls)`: Check if a class is a service
- `is_cf_module(cls)`: Check if a class is a module
- `is_cf_router(cls)`: Check if a class is a router
- `get_service_meta(cls)`: Get service metadata
- `get_module_meta(cls)`: Get module metadata

---

### Types

Data classes and type aliases.

**ServiceMeta:**
```python
@dataclass
class ServiceMeta:
    name: str                       # Auto-generated service name (e.g., "DatabaseService")
    deps: Dict[str, type] = {}      # Dependencies resolved from annotations
```

**ModuleMeta:**
```python
@dataclass
class ModuleMeta(ServiceMeta):
    services: List[type] = []       # Child services/modules
    config_cls: type = None         # Configuration class
```

**RouterMeta:**
```python
@dataclass
class RouterMeta(ServiceMeta):
    prefix: str = ""                # URL prefix
    tags: List[str] = []            # OpenAPI tags
    routes: List[Callable] = []     # Route handler methods
```

**ServiceEntry:**
```python
@dataclass
class ServiceEntry:
    cls: type                       # The service class
    name: str                       # Auto-generated name
    instance: object = None         # Service instance (None until configured)
    deps: List[type] = []           # Dependency types resolved from annotations
    dep_names: List[str] = []       # Annotation key names for dependency injection
```

**Type Aliases:**
- `HookFunction`: `Callable[..., object]`

---

## Engine Module

### Registry

Service registry class.

**Methods:**
- `__init__(parent: Registry = None)`: Create registry with optional parent
- `register(cls, *, meta=None)`: Register a service
- `get_by_name(name)`: Get service entry by name
- `get_by_class(cls)`: Get service entry by class
- `get_instance(cls)`: Get service instance by class
- `has(cls)`: Check if service is registered
- `all_entries()`: Get all service entries
- `names()`: Get all service names

**Special Methods:**
- `__len__()`: Number of services
- `__contains__(cls)`: Check if service is registered
- `__iter__()`: Iterate over service entries

---

### Resolver

Dependency resolution utilities.

**Functions:**
- `resolve_deps(cls) -> Dict[str, type]`: Read a class's `__annotations__` and return entries whose types are marked with `CF_SERVICE_MARKER`. This replaces the old `deps` list. Each returned key is the annotation attribute name that will be used for `setattr` injection.
- `topological_sort(registry) -> List[ServiceEntry]`: Sort services in dependency order using Kahn's algorithm. Uses `resolve_deps()` internally to build the dependency graph.

---

### Hooks

Lifecycle hook utilities.

**HookDict:**
```python
HookDict = Dict[LifecycleHook, Optional[Callable[..., object]]]
```

**LifecycleAware Protocol:**
```python
class LifecycleAware(Protocol):
    async def configure(self, config_instance=None) -> None: ...
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

**Functions:**
- `find_hooks(instance)`: Find all lifecycle hooks on an instance

---

### Utils

Utility functions.

**Functions:**
- `make_subclass(cls, base_class, meta, name, extra_marker=None)`: Create a subclass with framework metadata

---

## Version

```python
__version__: str
```

Current version of Canary Framework.

---

## Internal Attributes (For Advanced Use)

Decorated classes have these internal attributes set:

- `__cf_service__`: `True` if decorated with `@service()`
- `__cf_module__`: `True` if decorated with `@module()`
- `__cf_router__`: `True` if decorated with `@router()`
- `__cf_service_meta__`: Metadata object (ServiceMeta/ModuleMeta/RouterMeta)
- `__cf_name__`: Auto-generated service/module/router name

Hook methods have:
- `__cf_after_config__`: `True`
- `__cf_after_init__`: `True`
- `__cf_before_startup__`: `True`
- `__cf_before_shutdown__`: `True`

Route methods have:
- `__cf_route__`: `{"method": "GET", "path": "/path", ...}`

---

## Migration Notes (from v1 to v2)

Key changes from the old API:

| Old API (v1) | New API (v2) |
|---|---|
| `@service(name="foo")` | `@service()` — auto-named |
| `@service(name="foo", deps=[Bar])` | `@service()` with `bar: Bar` annotation |
| `@module(name="app", services=[...])` | `@module(services=[...])` — auto-named |
| `@module(name="app", deps=[...])` | Dependencies declared via annotations |
| `@router(name="api", prefix="/api", deps=[Svc])` | `@router(prefix="/api")` with `svc: Svc` annotation |
| `self.database_service` (snake_case injection) | `self.db`, `self.cache` (annotation key name) |
| `async def handler(self, request)` | `async def handler(self, ...)` — params auto-bound |
| `request.path_params["user_id"]` | `def handler(self, user_id: int)` |
| `request.query_params.get("page")` | `def handler(self, page: int = 1)` |
| `data = await request.json()` | `def handler(self, body: MyModel)` with `request_model` |
| `app.auth_module` / `app.auth_service` | `app.AuthModule` / `app.AuthService` (class name access) |
| `inject_deps(instance, entry, registry)` | `setattr(instance, key, resolved)` via annotation keys |
