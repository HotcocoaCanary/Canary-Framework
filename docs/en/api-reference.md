# API Reference

Complete API documentation for Canary Framework.

## Main Exports

```python
from canary_framework import (
    # Decorators
    config, service, module,
    before_startup, before_shutdown,

    # Router
    Router,

    # Config
    CanaryConfig,

    # Exceptions
    CanaryFrameworkError,
    DependencyInjectionError,
    CircularDependencyError,
    ConfigurationError,
    CanaryFrameworkError,
    ServiceNotFoundError,

    # Enums
    LifecycleHook,

    # Version
    __version__,
)
```

For `ServiceBase` and `ModuleBase`, import from `canary_framework.core`:

```python
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
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
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    pass
```

---

### @module

Marks a class as a module container.

**Signature:**
```python
def module(
    *,
    services: list[type] | None = None,
) -> Callable[[type], type[ModuleBase]]
```

**Parameters:**
- `services` (list[type], keyword-only): Services, routers, and sub-modules this module contains

The `name` and `deps` parameters have been removed. The module name is auto-generated as `ClassName` + `"Module"`.

**Example:**
```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

@module(services=[Database, Auth, Api])
class App(ModuleBase):
    pass
```

---

### Router

A route manager used as a class attribute inside `@service()` or `@module()` decorated classes.

**Signature:**
```python
class Router:
    def __init__(self, prefix: str = "", *, tags: list[str] | None = None)
```

**Parameters:**
- `prefix` (str, default `""`): URL prefix for all routes in this router
- `tags` (list[str] | None): OpenAPI tags for documentation grouping

**Example:**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["API"])

    @router.get("/users/{user_id}")
    async def get_user(self, user_id: int): ...
```

---

### Router HTTP Method Decorators

Router instances provide method decorators for defining routes: `@router.get`, `@router.post`, `@router.put`, `@router.delete`, `@router.patch`.

**Method signatures:**
```python
def get(path: str, *, summary=None, description=None, response_model=None,
        request_model=None, tags=None, deprecated=False, operation_id=None,
        responses=None, path_params=None, query_params=None) -> Callable
def post(...)  # same params
def put(...)   # same params
def delete(...)  # same params
def patch(...)  # same params
```

**Parameters same as before** but now called as `@router.get()`, `@router.post()`, etc. instead of standalone `@get()`, `@post()`.

Route handlers do **not** receive a `request` parameter. Path parameters, query parameters, and request body are auto-bound.

**Example:**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        pass

    @router.post("/", request_model=UserCreate)
    async def create_user(self, body: UserCreate):
        pass
```

---

### @config

Marks a class as a configuration class.

**Signature:**
```python
def config() -> Callable[[type], type[CanaryConfig]]
```

**Parameters:** None.

The config class must inherit from `CanaryConfig`. Sets `CF_CONFIG_MARKER` on the class.

**Example:**
```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "DEBUG"
```

---

### Lifecycle Hook Decorators

Mark methods as lifecycle hooks.

**Signatures:**
```python
def before_startup(func) -> HookFunction
def before_shutdown(func) -> HookFunction
```

**Example:**
```python
from canary_framework import service, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    async def init(self):
        await super().init()
        # connection setup

    async def shutdown(self):\n        await super().shutdown()
    async def disconnect(self):
        pass
```

---

## Base Classes

### CanaryConfig

Base class for framework configuration. All configuration classes must inherit from `CanaryConfig`.

```python
from canary_framework.common.config import CanaryConfig
```

**Fields (all optional, with defaults):**

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | `"127.0.0.1"` | Server bind address |
| `port` | `int` | `8000` | Server port (1-65535) |
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` | Framework log level |
| `openapi_title` | `str` | `"Canary Framework API"` | API title for OpenAPI schema |
| `openapi_version` | `str` | `"1.0.0"` | API version for OpenAPI schema |
| `openapi_description` | `str` | `""` | API description for OpenAPI schema |
| `openapi_servers` | `list[dict[str,str]]` | `[]` | OpenAPI server URLs |
| `openapi_security_schemes` | `dict[str,dict[str,object]]` | `{}` | OpenAPI security schemes |
| `docs_openapi_path` | `str` | `"/openapi.json"` | OpenAPI JSON endpoint path |
| `docs_swagger_path` | `str` | `"/docs"` | Swagger UI path |
| `docs_redoc_path` | `str` | `"/redoc"` | ReDoc path |
| `docs_swagger_css_cdn` | `str` | Swagger CSS CDN URL | CSS CDN URL |
| `docs_swagger_js_cdn` | `str` | Swagger JS CDN URL | JS CDN URL |
| `docs_redoc_cdn` | `str` | ReDoc JS CDN URL | ReDoc CDN URL |

Extra fields are allowed — you can add any custom configuration fields.

---

### ServiceBase

Base class for services.

**Import:**
```python
from canary_framework.core.service import ServiceBase
```

**Attributes:**
- `_cf_hooks`: Internal hook registry (lazily populated)
- `_cf_parent_registry`: Parent registry reference (set by parent module)

**Methods:**
- `async init()`: Initialize the service. Sets up logging and configs.
- `async startup()`: Start the service. Invokes `BEFORE_STARTUP` hook.
- `async shutdown()`: Shutdown the service. Invokes `BEFORE_SHUTDOWN` hook.
- `async __call__(scope, receive, send)`: ASGI 3 interface. Handles lifespan events and delegates other requests to `self.asgi_app`.
- `async _handle_lifespan(receive, send)`: Internal ASGI lifespan protocol handler.
- `async _invoke_hook(hook: LifecycleHook)`: Lazy hook discovery and invocation.

---

### ModuleBase

Base class for modules, extends `ServiceBase`.

**Import:**
```python
from canary_framework.core.module import ModuleBase
```

**Attributes:**
- `_cf_parent_registry`: Parent registry (if any)
- `_cf_registry`: Service registry for this module
- `_cf_startup_order`: List of service names in topological order
- `_cf_asgi_app`: Cached ASGI Starlette Router (lazily built)

**Properties:**
- `asgi_app`: Starlette `Router` with mounted child ASGI apps and root routes

**Methods:**
- `async init()`: Register services recursively, topological sort, instantiate, DI wire, init children. Config is auto-discovered from services list via `issubclass(CanaryConfig)`.
- `async startup()`: Start module and all children in topological order
- `async shutdown()`: Shutdown module and all children in reverse topological order
- `_register_entry_with_deps(cls, registry)`: Recursively register services with annotation-resolved dependencies

---

### Router

Route manager class used as a class attribute inside `@service()` or `@module()` decorated classes.
Does not extend `ServiceBase` — it is a standalone utility class.

**Import:**
```python
from canary_framework.core.router import Router
```

**Constructor:**
```python
class Router:
    def __init__(self, prefix: str = "", *, tags: list[str] | None = None)
```

**Parameters:**
- `prefix` (str, default `""`): URL prefix for all routes in this router
- `tags` (list[str] | None): OpenAPI tags for documentation grouping

**Methods:**
- `get(path, *, summary=None, description=None, response_model=None, request_model=None, tags=None, deprecated=False, operation_id=None, responses=None, path_params=None, query_params=None) -> Callable`: Decorator for GET routes
- `post(...)`: Decorator for POST routes (same parameters)
- `put(...)`: Decorator for PUT routes (same parameters)
- `delete(...)`: Decorator for DELETE routes (same parameters)
- `patch(...)`: Decorator for PATCH routes (same parameters)

**Example:**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["API"])

    @router.get("/users/{user_id}")
    async def get_user(self, user_id: int): ...
```

---

## Enums

### LifecycleHook

Lifecycle hook phases.

**Values:**
- `LifecycleHook.BEFORE_STARTUP`: `"before_startup"`
- `LifecycleHook.BEFORE_SHUTDOWN`: `"before_shutdown"`

---

## Exceptions

### CanaryFrameworkError

Base exception for all framework errors.

**Hierarchy:**
```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError       # Config load/validation failure
    ├── ServiceNotFoundError     # Service lookup failure
    ├── CircularDependencyError  # Topological sort cycle detected
    ├── DependencyInjectionError # DI wiring failure
    └── CanaryFrameworkError       # Hook raised unhandled exception
```

---

### DependencyInjectionError

Error during dependency injection.

---

### CircularDependencyError

Circular dependency detected during topological sort.

---

### CanaryFrameworkError

Error in a lifecycle hook. Wraps the original exception.

---

### ServiceNotFoundError

Service not found in registry.

---

### ConfigurationError

Configuration validation or loading error.

---

## Common Module

### Markers

Constants and helpers for identifying framework classes.

**Constants:**
- `CF_SERVICE_MARKER`: `"__cf_service__"` — set to `True` on all decorated classes
- `CF_SERVICE_META`: `"__cf_service_meta__"` — stores `ServiceMeta`/`ModuleMeta`/`RouterMeta`
- `CF_NAME_ATTR`: `"__cf_name__"` — auto-generated service/module/router name
- `ROUTE_ATTR`: `"__cf_route__"` — route metadata dict on handler methods
- `CF_CONFIG_MARKER`: `"__cf_config__"` — set to `True` on `@config` classes
- `CF_HOOK_MARKER_MAP`: Mapping of `LifecycleHook` to marker strings

**Functions:**
- `is_cf_service(cls)`: Check if a class has `CF_SERVICE_MARKER`
- `is_cf_module(cls)`: Check if a class has `ModuleMeta` in `CF_SERVICE_META` (isinstance check)
- `is_cf_router(cls)`: Check if a class has `RouterMeta` in `CF_SERVICE_META` (isinstance check)
- `get_service_meta(cls)`: Get service metadata
- `get_module_meta(cls)`: Get module metadata
- `get_router_meta(cls)`: Get router metadata
- `resolve_deps(cls) -> dict[str, type]`: Read `__annotations__` and return entries whose types have `CF_SERVICE_MARKER`

---

### Types

Data classes and type aliases.

**ServiceMeta:**
```python
@dataclass(slots=True)
class ServiceMeta:
    name: str  # Auto-generated: "DatabaseService"
```

**ModuleMeta:**
```python
@dataclass(slots=True)
class ModuleMeta(ServiceMeta):
    services: list[type] = []  # Child service classes
```

**RouterMeta:**
```python
@dataclass(slots=True)
class RouterMeta(ServiceMeta):
    prefix: str = ""              # URL prefix
    tags: list[str] = []          # OpenAPI tags
    routes: list[Callable] = []   # Route handler methods
```

**ServiceEntry:**
```python
@dataclass(slots=True)
class ServiceEntry:
    cls: type             # Service class
    name: str             # Auto-generated name
    instance: object = None  # Instance (None until initialized)
```

**Type Aliases:**
- `HookFunction`: `Callable[..., object]`

---

## Engine Module

### Registry

Service registry with parent chaining.

**Methods:**
- `__init__(parent: Registry = None)`: Create registry with optional parent
- `register(cls, *, meta: ServiceMeta)`: Register a service (idempotent)
- `get_by_name(name: str) -> ServiceEntry`: Lookup by name
- `get_by_class(cls: type) -> ServiceEntry`: Lookup by class (searches parent chain)
- `has(cls: type) -> bool`: Check if registered (searches parent chain)
- `all_entries() -> list[ServiceEntry]`: Get all entries in this registry
- `names() -> list[str]`: Get all service names

---

### Resolver

Dependency resolution utilities.

**Functions:**
- `resolve_deps(cls) -> dict[str, type]`: Read `cls.__annotations__` and return entries whose types have `CF_SERVICE_MARKER`. Each key is the annotation attribute name used for `setattr` injection.
- `topological_sort(registry: Registry) -> list[str]`: Sort services in dependency order using Kahn's algorithm. Uses `resolve_deps()` internally. Raises `CircularDependencyError` on cycles.

---

### Hooks

Lifecycle hook utilities.

**HookDict:**
```python
HookDict = dict[LifecycleHook, Callable[..., object] | None]
```

**LifecycleAware Protocol:**
```python
class LifecycleAware(Protocol):
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

**Functions:**
- `(instance: object) -> HookDict`: Traverse MRO to find lifecycle hook methods

---

### Routing

Route path parsing.

**Functions:**
- `parse_route_path(path: str) -> tuple[str, list[str], list[str]]`: Parse a route path, returning `(starlette_path, path_params, query_params)`. Supports `?param={param}&param2={param2}` syntax for query parameters:
  - Input: `"/op/{kb_id}?count={count}&page={page}"`
  - Output: `("/op/{kb_id}", ["kb_id"], ["count", "page"])`

---

## Version

```python
__version__: str
```

Current version of Canary Framework.

---

## Internal Attributes (For Advanced Use)

Decorated classes have these internal attributes set:

- `__cf_service__`: `True` if decorated with `@service()` or `@module()`
- `__cf_service_meta__`: Metadata object (`ServiceMeta`/`ModuleMeta`/`RouterMeta`)
- `__cf_name__`: Auto-generated name (e.g., `"DatabaseService"`)

Hook methods have:
- `__cf_before_startup__`: `True`
- `__cf_before_shutdown__`: `True`

Route methods have:
- `__cf_route__`: `{"method": "GET", "path": "/path", ...}`

Config classes have:
- `__cf_config__`: `True`

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
| `@router(docs=True)` | Docs auto-enabled by default |
| `self.database_service` (snake_case injection) | `self.db`, `self.cache` (annotation key name) |
| `async def handler(self, request)` | `async def handler(self, ...)` — params auto-bound |
| `request.path_params["user_id"]` | `def handler(self, user_id: int)` |
| `request.query_params.get("page")` | `def handler(self, page: int = 1)` |
| `data = await request.json()` | `def handler(self, body: MyModel)` with `request_model` |
| `uvicorn.run("main:App")` | `uvicorn.run(app, lifespan="on")` |
| Plain dict passed to `configure()` | `CanaryConfig` subclass required |
| `await app.configure(cfg)` | `await app.init()` — single init call |
| `make_subclass()` utility | Removed — explicit inheritance |
| `CF_MODULE_MARKER` / `CF_ROUTER_MARKER` | Removed — `isinstance` checks on meta types |
| `@router(prefix="/api")` class decorator | `router = Router(prefix="/api")` class attribute |
| `class X(RouterBase)` | `class X(ServiceBase)` with `router` attribute |
| `@get("/path")` | `@router.get("/path")` |
| `@post("/path")` | `@router.post("/path")` |
