# Modules

Modules are containers that organize and compose services together. They manage the lifecycle of their child services and provide a way to structure your application hierarchically.

## Defining a Module

Use the `@module` decorator to define a module:

```python
from canary_framework import module

@module(name="auth_module", services=[...])
class AuthModule:
    pass
```

### Module Parameters

- `name`: (required) A unique identifier for the module
- `services`: (optional) A list of service or module classes this module contains
- `deps`: (optional) A list of services or modules this module depends on

## Module Composition

Modules can contain services and other modules, creating a hierarchical structure:

```python
from canary_framework import module, service, router

# Core services
@service(name="database")
class DatabaseService:
    pass

@service(name="cache")
class CacheService:
    pass

# Auth module
@service(name="auth_service", deps=[DatabaseService])
class AuthService:
    pass

@router(name="auth_api", prefix="/auth", deps=[AuthService])
class AuthRouter:
    pass

@module(name="auth", services=[AuthService, AuthRouter])
class AuthModule:
    pass

# Posts module
@service(name="posts_service", deps=[DatabaseService, CacheService])
class PostsService:
    pass

@router(name="posts_api", prefix="/posts", deps=[PostsService])
class PostsRouter:
    pass

@module(name="posts", services=[PostsService, PostsRouter])
class PostsModule:
    pass

# Main application module
@module(
    name="app",
    services=[
        DatabaseService,
        CacheService,
        AuthModule,
        PostsModule
    ]
)
class AppModule:
    pass
```

## Module Lifecycle

Modules coordinate the lifecycle of their child services. When a module's lifecycle methods are called, they propagate to all child services in topological order.

```python
app = AppModule()

# 1. Configure phase: configures all services in dependency order
await app.configure(config)

# 2. Init phase: initializes all services
await app.init()

# 3. Startup phase: starts all services
await app.startup()

# ... application runs ...

# 4. Shutdown phase: shuts down all services in reverse order
await app.shutdown()
```

## Module as ASGI App

A module can be used directly as an ASGI application. It automatically mounts all child routers:

```python
import uvicorn

# Run the module as an ASGI app
uvicorn.run("main:AppModule", host="0.0.0.0", port=8000)
```

The module will:
1. Collect all routers from its services
2. Mount them at paths based on their service names
3. Handle ASGI requests

## Module Base Class

When you decorate a class with `@module`, it automatically inherits from `ModuleBase`, which provides:

- `config` attribute: Access to configuration
- `configure(config)` method: Configures the module and all services
- `init()` method: Initializes the module and all services
- `startup()` method: Starts the module and all services
- `shutdown()` method: Shuts down the module and all services
- `asgi_app` property: Access to the ASGI application

## Dependency Sharing

Services in a module share dependencies. If multiple services depend on the same service, only one instance is created and shared:

```python
@service(name="database")
class DatabaseService:
    pass

@service(name="service_a", deps=[DatabaseService])
class ServiceA:
    pass

@service(name="service_b", deps=[DatabaseService])
class ServiceB:
    pass

@module(name="app", services=[DatabaseService, ServiceA, ServiceB])
class AppModule:
    pass

# Both ServiceA and ServiceB will receive the same DatabaseService instance
```

## Complete Example

```python
from canary_framework import module, service, router, get

# Services
@service(name="db")
class Database:
    pass

@service(name="user_repo", deps=[Database])
class UserRepository:
    pass

@service(name="user_service", deps=[UserRepository])
class UserService:
    pass

# Router
@router(name="users", prefix="/api/users", deps=[UserService])
class UsersRouter:
    @get("/")
    async def list_users(self, request):
        return {"users": []}

# Modules
@module(name="users_module", services=[UserRepository, UserService, UsersRouter])
class UsersModule:
    pass

@module(name="app", services=[Database, UsersModule])
class App:
    pass
```

## Best Practices

1. **Layered Architecture**: Organize modules by feature (e.g., auth, users, posts)
2. **Single Responsibility**: Each module focuses on one functional area
3. **Module Composition**: Build large applications by composing smaller modules
4. **Config Isolation**: Provide isolated configuration space for each module
5. **Test Isolation**: Each module can be tested independently
