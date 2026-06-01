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
def service(name: str, *, deps: List[type] = None) -> Callable[[type], type[ServiceBase]]
```

**Parameters:**
- `name` (str, required): Unique identifier for the service
- `deps` (List[type], optional): List of service classes this service depends on

**Example:**
```python
@service(name="database", deps=[ConfigService])
class DatabaseService:
    pass
```

---

### @module

Marks a class as a module.

**Signature:**
```python
def module(
    name: str,
    *,
    deps: List[type] = None,
    services: List[type] = None
) -> Callable[[type], type[ModuleBase]]
```

**Parameters:**
- `name` (str, required): Unique identifier for the module
- `deps` (List[type], optional): Dependencies for the module
- `services` (List[type], optional): Services/modules this module contains
- `config` (type, optional): Configuration class for the module

**Example:**
```python
@module(name="app", services=[DatabaseService, ApiRouter])
class AppModule:
    pass
```

---

### @router

Marks a class as a router.

**Signature:**
```python
def router(
    name: str = "",
    prefix: str = "",
    *,
    deps: List[type] = None,
    tags: List[str] = None
) -> Callable[[type], type[RouterBase]]
```

**Parameters:**
- `prefix` (str, optional): URL prefix for all routes
- `name` (str, optional): Unique identifier for the router
- `deps` (List[type], optional): Dependencies for the router
- `tags` (List[str], optional): OpenAPI tags for documentation

**Example:**
```python
@router(name="api", prefix="/api", deps=[UserService])
class ApiRouter:
    pass
```

---

### HTTP Method Decorators

Mark methods as route handlers.

**Signatures:**
```python
def get(path: str) -> Callable[[HookFunction], HookFunction]
def post(path: str) -> Callable[[HookFunction], HookFunction]
def put(path: str) -> Callable[[HookFunction], HookFunction]
def delete(path: str) -> Callable[[HookFunction], HookFunction]
def patch(path: str) -> Callable[[HookFunction], HookFunction]
```

**Parameters:**
- `path` (str, required): URL path for the route

**Example:**
```python
@router(name="users")
class UsersRouter:
    @get("/{user_id}")
    async def get_user(self, request):
        pass
    
    @post("/")
    async def create_user(self, request):
        pass
```

---

### Lifecycle Hook Decorators

Mark methods as lifecycle hooks.

**Signatures:**
```python
def after_config(func: HookFunction) -> HookFunction
def after_init(func: HookFunction) -> HookFunction
def before_startup(func: HookFunction) -> HookFunction
def before_shutdown(func: HookFunction) -> HookFunction
```

**Example:**
```python
@service(name="database")
class DatabaseService:
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
- `_register_entry_with_deps(cls, registry)`: Recursively register services

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
- `CF_SERVICE_MARKER`: "__cf_service__"
- `CF_MODULE_MARKER`: "__cf_module__"
- `CF_ROUTER_MARKER`: "__cf_router__"
- `CF_NAME_ATTR`: "__cf_name__"
- `ROUTE_ATTR`: "__cf_route__"
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
    name: str
    deps: List[type] = field(default_factory=list)
```

**ModuleMeta:**
```python
@dataclass
class ModuleMeta(ServiceMeta):
    services: List[type] = field(default_factory=list)
    config_cls: type = None
```

**RouterMeta:**
```python
@dataclass
class RouterMeta(ServiceMeta):
    prefix: str = ""
    tags: List[str] = field(default_factory=list)
    routes: List[HookFunction] = field(default_factory=list)
```

**ServiceEntry:**
```python
@dataclass
class ServiceEntry:
    cls: type
    name: str
    instance: object = None
    deps: List[type] = field(default_factory=list)
    dep_names: List[str] = field(default_factory=list)
```

**Type Aliases:**
- `HookFunction`: Callable[..., object]

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

### Injector

Dependency injection utilities.

**Functions:**
- `to_snake(name)`: Convert camelCase to snake_case
- `topological_sort(registry)`: Sort services in dependency order
- `inject_deps(instance, entry, registry)`: Inject dependencies into instance

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

- `__cf_service__`: `True` if decorated with @service
- `__cf_module__`: `True` if decorated with @module
- `__cf_router__`: `True` if decorated with @router
- `__cf_service_meta__`: Metadata object (ServiceMeta/ModuleMeta/RouterMeta)
- `__cf_name__`: Service/module name

Hook methods have:
- `__cf_after_config__`: `True`
- `__cf_after_init__`: `True`
- `__cf_before_startup__`: `True`
- `__cf_before_shutdown__`: `True`

Route methods have:
- `__cf_route__`: `{"method": "GET", "path": "/path"}`
