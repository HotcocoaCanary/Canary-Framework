# Lifecycle Management

Canary Framework provides a comprehensive lifecycle management system for services and modules.

## Lifecycle Phases

Every service and module goes through these phases:

```
Instantiation → Initialization → Startup → Shutdown
```

### 1. Instantiation

The service instance is created with `__init__()`:

```python
@service()
class MyService(ServiceBase):
    def __init__(self):
        self.connected = False
        self.data = []
```

### 2. Initialization

The `init()` method is called after all services are instantiated. Override it to set up connections, seed data, or perform any post-instantiation setup:

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class UserService(ServiceBase):
    db: Database

    async def init(self):
        await super().init()
        if not await self.db.has_users():
            await self.db.create_default_users()
```

### 3. Startup

The `startup()` method is called when the application is ready to start:

```python
@service()
class MyService(ServiceBase):
    async def startup(self):
        pass
```

    async def startup(self):
        await super().startup()
        assert self.db.connection is not None
        assert self.cache.connection is not None
```

### 4. Shutdown

The `shutdown()` method is called when the application is stopping.

```python
@service()
class Database(ServiceBase):
    async def shutdown(self):
        await super().shutdown()
        await self.connection.close()
```

## Module Lifecycle

Modules coordinate the lifecycle of their child services:

```python
@module(services=[ServiceA, ServiceB])
class App(ModuleBase):
    pass

app = App()

# Initialize all services
await app.init()

# Start all services
await app.startup()

# ... run app ...

# Shutdown all services in reverse order
await app.shutdown()
```

The execution order follows topological sort:
- **Init**: dependencies first (A → B)
- **Startup**: dependencies first (A → B)
- **Shutdown**: reverse order (B → A)

## Complete Lifecycle Example

```python
from canary_framework import (
    service, module,
    before_startup, before_shutdown
)
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase

calls = []

@service()
class A(ServiceBase):
    async def init(self):
        await super().init()
        calls.append("A: init")

    async def startup(self):\n        await super().startup()
    def startup_a(self):
        calls.append("A: before_startup")

    async def shutdown(self):\n        await super().shutdown()
    def shutdown_a(self):
        calls.append("A: before_shutdown")

@service()
class B(ServiceBase):
    a: A  # B depends on A

    async def init(self):
        await super().init()
        calls.append("B: init")

    async def startup(self):\n        await super().startup()
    def startup_b(self):
        calls.append("B: before_startup")

    async def shutdown(self):\n        await super().shutdown()
    def shutdown_b(self):
        calls.append("B: before_shutdown")

@module(services=[A, B])
class App(ModuleBase):
    pass

# Run lifecycle
app = App()
await app.init()
await app.startup()
await app.shutdown()

# Resulting order:
# A: init
# B: init
# A: before_startup
# B: before_startup
# B: before_shutdown
# A: before_shutdown
```

## ASGI Lifecycle

When running as an ASGI application, the framework handles the lifecycle through `ServiceBase.__call__`:

```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8000

@module(services=[AppConfig, ...])
class App(ModuleBase):
    config: AppConfig

async def setup():
    app = App()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn

    app = asyncio.run(setup())
    uvicorn.run(app, host="0.0.0.0", port=8000, lifespan="on")
```

`ServiceBase.__call__` handles the ASGI lifespan:
1. Call `startup()` when the server starts
2. Call `shutdown()` when the server stops

## Configuration

Config is a regular DI service. Add it to your module and inject it:

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    database_url: str = "sqlite:///mydb.db"
    debug: bool = True

@service()
class Database(ServiceBase):
    config: AppConfig

    async def init(self):
        await super().init()
        url = self.config.database_url
        self.connection = await connect(url)

app = App()
await app.init()
await app.startup()
await app.shutdown()

The framework automatically configures logging during `init()`. No manual
`logging.basicConfig()` is needed.

**Default behavior**: When you call `app.init()`, the framework adds a
`StreamHandler` to the `cf` logger with `INFO` level:

```python
from canary_framework import module

@module(services=[AppConfig, ...])
class App(ModuleBase):
    config: AppConfig

app = App()
await app.init()
# Framework logs now visible on stdout:
# [2026-06-02 13:00:00] cf.module             INFO     Initializing module: AppModule
```

**Custom log level**: Set `log_level` on your config object to control the
framework log level:

```python
@config()
class AppConfig(CanaryConfig):
    log_level: str = "DEBUG"  # Show debug-level framework logs
    # ... other config fields ...
```

Valid levels: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`.

**Manual handler**: If you have already configured a handler on the root logger
or the `cf` logger, the framework skips its own setup.

## Error Handling

If a hook raises an exception, it's wrapped in `CanaryFrameworkError`:

```python
from canary_framework.common import CanaryFrameworkError

try:
    await app.init()
except CanaryFrameworkError as e:
    print(f"Lifecycle error: {e}")
```

## Best Practices

1. **Override `init()` for connections and data setup**: Establish connections and set up initial data during init
2. **Use `async def startup(self):\n        await super().startup()` for validation**: Verify everything is ready before serving
3. **Use `async def shutdown(self):\n        await super().shutdown()` for cleanup**: Gracefully close connections and save state
4. **Keep hooks focused**: Each hook should do one thing well
5. **Handle errors gracefully**: Catch and log exceptions in hooks
