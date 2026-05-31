# Core Concepts

This document explains the core design principles and internal architecture of Canary Framework.

## Design Principles

### 1. Decorator-Driven

The framework uses decorators to keep your code clean and declarative:

```python
@service(name="my_service")
class MyService:
    pass
```

Instead of complex configuration files, your code itself is the configuration.

### 2. Async-First

Everything is built around async/await for high performance:

```python
@service(name="my_service")
class MyService:
    async def do_something(self):
        await some_async_operation()
```

### 3. Explicit Dependencies

Dependencies are declared explicitly, making your code easier to understand and test:

```python
@service(name="my_service", deps=[DatabaseService, CacheService])
class MyService:
    pass
```

### 4. Convention Over Configuration

Sensible defaults reduce boilerplate:
- Dependencies are auto-injected with snake_case names
- Lifecycle methods follow a standard pattern
- Routers are auto-mounted at predictable paths

### 5. Composability

Build complex systems by composing simple modules:

```python
@module(name="app", services=[AuthModule, PostsModule, CommentsModule])
class AppModule:
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
│  │ Registry │  │ Injector │  │ Lifecycle│  │ Hooks  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Starlette/ASGI                      │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Decorators

Decorators transform plain classes into framework-aware components:

- `@service`: Marks a class as a service
- `@module`: Marks a class as a module
- `@router`: Marks a class as a router
- `@get/@post/etc`: Marks methods as route handlers
- `@after_config/etc`: Marks methods as lifecycle hooks

### 2. Base Classes

Decorated classes automatically inherit from base classes:

- `ServiceBase`: Base for services with lifecycle methods
- `ModuleBase`: Base for modules that coordinate services
- `RouterBase`: Base for routers with ASGI integration

### 3. Engine

The engine manages the framework's core operations:

- **Registry**: Service registration and lookup
- **Injector**: Dependency injection and topological sorting
- **Hooks**: Lifecycle hook discovery and execution
- **Utils**: Helper functions (name conversion, etc.)

## How It Works: Module Startup

Let's trace through what happens when you start a module:

### Step 1: Module Instantiation

```python
app = AppModule()
```

- Creates an instance of your module class
- The class inherits from `ModuleBase` via the decorator

### Step 2: Configuration

```python
await app.configure(config)
```

1. Collects all services from the module's `services` list
2. Builds a dependency graph by traversing service dependencies
3. Performs a topological sort to determine startup order
4. Creates instances of all services
5. Injects dependencies into each service
6. Calls `configure()` on each service in order
7. Runs `@after_config` hooks

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
- Mounts child routers at their service names
- Routes requests to handlers

### Step 6: Shutdown

```python
await app.shutdown()
```

1. Runs `@before_shutdown` hooks
2. Calls `shutdown()` on each service in reverse order

## Metadata System

The framework stores metadata on decorated classes:

```python
@service(name="my_service", deps=[DatabaseService])
class MyService:
    pass

# Metadata is stored as attributes
hasattr(MyService, "__cf_service__")  # True
hasattr(MyService, "__cf_service_meta__")  # True
```

Metadata classes:
- `ServiceMeta`: Metadata for services
- `ModuleMeta`: Metadata for modules (extends ServiceMeta)
- `RouterMeta`: Metadata for routers (extends ServiceMeta)

## Marker System

Markers identify what type a class is:

- `__cf_service__`: Identifies a service class
- `__cf_module__`: Identifies a module class
- `__cf_router__`: Identifies a router class

Helper functions:
- `is_cf_service()`: Check if a class is a service
- `is_cf_module()`: Check if a class is a module
- `is_cf_router()`: Check if a class is a router

## Dependency Injection Flow

```
1. Collect all services
   ↓
2. Register in registry
   ↓
3. Build dependency graph
   ↓
4. Topological sort
   ↓
5. Create instances
   ↓
6. Inject dependencies
   ↓
7. Run lifecycle
```

## ASGI Integration

The framework integrates with Starlette for ASGI support:

1. `RouterBase` collects route handlers
2. Converts them to Starlette `Route` objects
3. Creates a Starlette `Router`
4. `ModuleBase` mounts child routers
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
- Dependencies are explicit, easy to mock
- Lifecycle methods can be called individually
- No global state, tests are isolated
