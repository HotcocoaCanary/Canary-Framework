# Modules

Modules are containers that organize and compose services together. They manage the lifecycle of their child services and provide a way to structure your application hierarchically.

## Defining a Module

Use the `@module()` decorator to define a module:

```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

@module(services=[Database, UserRepo, AuthApi])
class Auth(ModuleBase):
    pass
```

- `@module(services=[...])` — only `services` parameter needed
- Name is auto-generated from the class name (`ClassName` + `"Module"`)
- Module is automatically named `AuthModule`

## Module Composition

Modules can contain services and other modules, creating a hierarchical structure:

```python
from canary_framework import module, service
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router

# Core services
@service()
class Database(ServiceBase):
    pass

@service()
class Cache(ServiceBase):
    pass

# Auth module
@service()
class AuthService(ServiceBase):
    db: Database

@service()
class AuthApi(ServiceBase):
    router = Router(prefix="/auth")
    auth: AuthService

@module(services=[AuthService, AuthApi])
class Auth(ModuleBase):
    pass

# Posts module
@service()
class PostsService(ServiceBase):
    db: Database
    cache: Cache

@service()
class PostsApi(ServiceBase):
    router = Router(prefix="/posts")
    posts: PostsService

@module(services=[PostsService, PostsApi])
class Posts(ModuleBase):
    pass

# Main application module
@module(services=[Database, Cache, Auth, Posts])
class App(ModuleBase):
    pass
```

## Module Children Access

Child services and sub-modules are accessible directly by their class name on the module instance:

```python
app = App()
await app.init()

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

# 1. Init phase: initializes all services in dependency order
await app.init()

# 2. Startup phase: starts all services
await app.startup()

# ... application runs ...

# 3. Shutdown phase: shuts down all services in reverse order
await app.shutdown()
```

## Module as ASGI App

A module can be used directly as an ASGI application. It automatically mounts all child routers:

```python
@module(services=[...])
class App(ModuleBase):
    pass

async def setup():
    app = App()
    await app.init()
    return app

import asyncio
import uvicorn

app = asyncio.run(setup())
uvicorn.run(app, host="0.0.0.0", port=8080, lifespan="on")
```

The module will:
1. Collect all routers from its services
2. Mount them at paths based on their prefix
3. Handle ASGI requests

## Module Base Class

Classes decorated with `@module()` must explicitly inherit from `ModuleBase`, which provides:

- `init()` method: Initializes the module and all services
- `startup()` method: Starts the module and all services
- `shutdown()` method: Shuts down the module and all services
- `asgi_app` property: Access to the ASGI application

## Dependency Sharing

Services in a module share dependencies. If multiple services depend on the same service, only one instance is created and shared:

```python
@service()
class Database(ServiceBase):
    pass

@service()
class ServiceA(ServiceBase):
    db: Database

@service()
class ServiceB(ServiceBase):
    db: Database

@module(services=[Database, ServiceA, ServiceB])
class App(ModuleBase):
    pass

# Both ServiceA and ServiceB receive the same Database instance
```

## Complete Example

```python
from canary_framework import module, service
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router

# Services
@service()
class Database(ServiceBase):
    async def query(self, sql):
        pass

@service()
class UserRepo(ServiceBase):
    db: Database

@service()
class UserService(ServiceBase):
    repo: UserRepo

# Router
@service()
class Users(ServiceBase):
    router = Router(prefix="/api/users")
    user: UserService

    @router.get("/")
    async def list_users(self):
        return {"users": []}

# Modules
@module(services=[UserRepo, UserService, Users])
class UsersMod(ModuleBase):
    pass

@module(services=[Database, UsersMod])
class App(ModuleBase):
    pass
```

## Best Practices

1. **Layered Architecture**: Organize modules by feature (e.g., auth, users, posts)
2. **Single Responsibility**: Each module focuses on one functional area
3. **Module Composition**: Build large applications by composing smaller modules
4. **Config Isolation**: Provide isolated configuration space for each module
5. **Test Isolation**: Each module can be tested independently
6. **Use descriptive annotation names**: `db`, `repo`, `service` — not `d1`, `d2`
