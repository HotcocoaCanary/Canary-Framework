# Modules

Modules are containers that organize and compose services together. They manage the lifecycle of their child services and provide a way to structure your application hierarchically.

## Defining a Module

Use the `@module()` decorator to define a module:

```python
from canary_framework import module

@module(services=[Database, UserRepo, AuthApi])
class Auth:
    pass
```

- `@module(services=[...])` — only `services` parameter needed
- No `name` or `deps` parameters — name is auto-derived (`ClassName` + `"Module"`)
- Module is automatically named `AuthModule`

## Module Composition

Modules can contain services and other modules, creating a hierarchical structure:

```python
from canary_framework import module, service, router

# Core services
@service()
class Database:
    pass

@service()
class Cache:
    pass

# Auth module
@service()
class AuthService:
    db: Database

@router(prefix="/auth")
class AuthApi:
    auth: AuthService

@module(services=[AuthService, AuthApi])
class Auth:
    pass

# Posts module
@service()
class PostsService:
    db: Database
    cache: Cache

@router(prefix="/posts")
class PostsApi:
    posts: PostsService

@module(services=[PostsService, PostsApi])
class Posts:
    pass

# Main application module
@module(services=[Database, Cache, Auth, Posts])
class App:
    pass
```

## Module Children Access

Child services and sub-modules are accessible directly by their class name on the module instance:

```python
app = App()
await app.configure(config)

# Access child services by class name (not snake_case)
app.Database    # Database service instance
app.Cache       # Cache service instance
app.Auth        # Auth sub-module instance
app.Posts       # Posts sub-module instance
```

## Module Lifecycle

Modules coordinate the lifecycle of their child services. When a module's lifecycle methods are called, they propagate to all child services in topological order.

```python
app = App()

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

uvicorn.run("main:App", host="0.0.0.0", port=8000)
```

The module will:
1. Collect all routers from its services
2. Mount them at paths based on their prefix
3. Handle ASGI requests

## Module Base Class

When you decorate a class with `@module()`, it automatically inherits from `ModuleBase`, which provides:

- `config` attribute: Access to configuration
- `configure(config_instance=None)` method: Configures the module and all services
- `init()` method: Initializes the module and all services
- `startup()` method: Starts the module and all services
- `shutdown()` method: Shuts down the module and all services
- `asgi_app` property: Access to the ASGI application

## Dependency Sharing

Services in a module share dependencies. If multiple services depend on the same service, only one instance is created and shared:

```python
@service()
class Database:
    pass

@service()
class ServiceA:
    db: Database

@service()
class ServiceB:
    db: Database

@module(services=[Database, ServiceA, ServiceB])
class App:
    pass

# Both ServiceA and ServiceB receive the same Database instance
```

## Complete Example

```python
from canary_framework import module, service, router, get

# Services
@service()
class Database:
    async def query(self, sql):
        pass

@service()
class UserRepo:
    db: Database

@service()
class UserService:
    repo: UserRepo

# Router
@router(prefix="/api/users")
class Users:
    user: UserService

    @get("/")
    async def list_users(self):
        return {"users": []}

# Modules
@module(services=[UserRepo, UserService, Users])
class UsersModule:
    pass

@module(services=[Database, UsersModule])
class App:
    pass
```

## Best Practices

1. **Layered Architecture**: Organize modules by feature (e.g., auth, users, posts)
2. **Single Responsibility**: Each module focuses on one functional area
3. **Module Composition**: Build large applications by composing smaller modules
4. **Config Isolation**: Provide isolated configuration space for each module
5. **Test Isolation**: Each module can be tested independently
6. **Use descriptive annotation names**: `db`, `repo`, `service` — not `d1`, `d2`
