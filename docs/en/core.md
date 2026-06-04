# Core Concepts

This document explains the core design principles and internal architecture of Canary Framework.

## Design Principles

### 1. Decorator-Driven

The framework uses decorators to keep your code clean and declarative:

```python
@service()
class MyService(ServiceBase):
    pass
```

Your code itself is the configuration — no XML, JSON, or YAML needed.

### 2. Async-First

Everything is built around async/await for high performance:

```python
@service()
class MyService(ServiceBase):
    async def do_something(self):
        await some_async_operation()
```

### 3. Annotation-Based DI

Dependencies are declared with Python type annotations, not separate lists:

```python
@service()
class UserService(ServiceBase):
    db: Database      # Auto-resolved and injected
    cache: Cache      # Auto-resolved and injected
```

### 4. Automatic Naming

Names are derived from class names — no manual strings:

- `@service()` + class `Database` → name `DatabaseService`
- `@module(services=[...])` + class `App` → name `AppModule`
- `@router(prefix="/api")` + class `Api` → name `ApiRouter`

### 5. Composability

Build complex systems by composing simple modules:

```python
@module(services=[AuthModule, PostsModule, CommentsModule])
class App(ModuleBase):
    pass
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Application                         │
├─────────────────────────────────────────────────────────┤
│                      Modules                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Auth Module  │  │ Posts Module │  │   ...        │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Services                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Service    │  │   Service    │  │   Router     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Engine                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Registry │  │ Resolver │  │ Lifecycle│  │ Hooks  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Starlette/ASGI                      │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Decorators

Decorators transform plain classes into framework-aware components:

- `@service()`: Marks a class as a service
- `@module(services=[...])`: Marks a class as a module container
- `@router(prefix="", *, tags=None)`: Marks a class as a router
- `@get/@post/etc`: Marks methods as route handlers
- `@after_config/@after_init/@before_startup/@before_shutdown`: Marks methods as lifecycle hooks

### 2. Base Classes

Classes decorated with `@service()`, `@module()`, or `@router()` must explicitly inherit from base classes:

- `ServiceBase`: Base for services with lifecycle methods
- `ModuleBase`: Base for modules that coordinate services
- `RouterBase`: Base for routers with ASGI integration

### 3. Engine

The engine manages the framework's core operations:

- **Registry**: Service registration and lookup
- **Resolver**: `resolve_deps()` reads annotations to discover dependencies
- **Injector**: `topological_sort()` builds dependency graph and orders instantiation
- **Hooks**: Lifecycle hook discovery and execution

## Dependency Injection Flow

The new DI system is annotation-driven:

```
1. Iterate over declared services
   ↓
2. For each service, resolve_deps(cls) reads type annotations
   ↓
3. Filter: keep only types marked with CF_SERVICE_MARKER
   ↓
4. Register each discovered dependency recursively
   ↓
5. topological_sort(registry) builds a dependency graph
   ↓
6. Instantiate services in topological order
   ↓
7. For each dependency: setattr(instance, annotation_key, dependency_instance)
   ↓
8. Run lifecycle phases
```

### resolve_deps(cls)

This function reads a class's `__annotations__` dict and returns only those entries
whose type is decorated with `CF_SERVICE_MARKER`. For example:

```python
@service()
class Auth(ServiceBase):
    db: Database   # ✓ CF_SERVICE_MARKER — included
    x: int         # ✗ Not a service — excluded

# resolve_deps(Auth) returns: {"db": Database}
```

### topological_sort(registry)

Uses Kahn's algorithm with `resolve_deps()` to:
1. Build the full dependency graph from all registered services
2. Determine instantiation order
3. Detect circular dependencies

### setattr Injection

Dependencies are injected using the annotation key name — no snake_case conversion:

```python
@service()
class UserService(ServiceBase):
    db: Database   # Injected as self.db
    repo: UserRepo # Injected as self.repo
```

## How It Works: Module Startup

Let's trace through what happens when you start a module:

### Step 1: Module Instantiation

```python
app = App()
```

### Step 2: Configuration

```python
await app.configure(config)  # config must be CanaryConfig | None
```

1. Collects all services from the module's `services` list
2. For each service, calls `resolve_deps(cls)` to discover annotations
3. Recursively registers all discovered dependency types
4. Calls `topological_sort(registry)` to determine startup order
5. Creates instances of all services in order
6. Calls `setattr` to inject each dependency with its annotation key name
7. Calls `configure()` on each service in order
8. Runs `@after_config` hooks

### Step 3: Initialization

```python
await app.init()
```

1. Calls `init()` on each service in order
2. Runs `@after_init` hooks

### Step 4: Startup

```python
await app.startup()
```

1. Runs `@before_startup` hooks
2. Calls `startup()` on each service in order

### Step 5: Request Handling

The module acts as an ASGI app:
- Collects all routers from services
- Creates a Starlette router
- Mounts child routers at their prefix paths
- Routes requests to handlers with auto-bound parameters

### Step 6: Shutdown

```python
await app.shutdown()
```

1. Runs `@before_shutdown` hooks
2. Calls `shutdown()` on each service in reverse order

## Metadata System

The framework stores metadata on decorated classes:

```python
@service()
class MyService(ServiceBase):
    pass

hasattr(MyService, "__cf_service__")     # True
hasattr(MyService, "__cf_service_meta__")  # True
```

Metadata classes:
- `ServiceMeta`: Metadata for services (auto-generated name, dependencies from annotations)
- `ModuleMeta`: Metadata for modules (extends ServiceMeta, adds services list)
- `RouterMeta`: Metadata for routers (extends ServiceMeta, adds prefix, tags, routes)

## Marker System

The framework uses `CF_SERVICE_MARKER` to identify service classes. Type checking is done using `isinstance` against the base classes:

- `isinstance(obj, ServiceBase)`: Check if an object is a framework service
- `isinstance(obj, ModuleBase)`: Check if an object is a framework module
- `isinstance(obj, RouterBase)`: Check if an object is a framework router

Helper functions:
- `is_cf_service(cls)`: Check if a class is a framework service
- `is_cf_module(cls)`: Check if a class is a framework module
- `is_cf_router(cls)`: Check if a class is a framework router

## ASGI Integration

The framework integrates with Starlette for ASGI support:

1. `RouterBase` collects route handlers with auto-bound parameter info
2. Converts them to Starlette `Route` objects
3. Creates a Starlette `Router`
4. `ModuleBase` and `RouterBase` inherit `ServiceBase.__call__` which handles ASGI requests and lifespan events
5. The module acts as an ASGI application

## Error Handling

The framework defines custom exceptions:

- `CanaryFrameworkError`: Base exception
- `DependencyInjectionError`: Error during DI
- `CircularDependencyError`: Circular dependency detected
- `LifecycleHookError`: Error in lifecycle hook
- `ServiceNotFoundError`: Service not found in registry

## Extensibility

The framework is designed to be extensible:

- Create custom base classes by inheriting from `ServiceBase`
- Build custom decorators that wrap the built-in ones
- Create composite modules that package related services
- Integrate with any ASGI-compatible server

## Performance Considerations

- **Startup**: O(n log n) due to topological sort
- **Runtime**: O(1) lookup for services
- **Memory**: Services are singletons, so memory is efficient
- **Requests**: Handled by Starlette, very fast

## Testing Strategy

The framework is designed for testability:

- Services are plain classes, easy to instantiate
- Dependencies are explicit via annotations, easy to mock
- Lifecycle methods can be called individually
- No global state, tests are isolated
