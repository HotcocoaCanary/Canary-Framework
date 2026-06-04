# Lifecycle Management

Canary Framework provides a comprehensive lifecycle management system for services and modules.

## Lifecycle Phases

Every service and module goes through these phases:

```
Instantiation → Configuration → Initialization → Startup → Shutdown
```

### 1. Instantiation

The service instance is created with `__init__()`:

```python
@service()
class MyService:
    def __init__(self):
        self.connected = False
        self.data = []
```

### 2. Configuration

The `configure(config_instance)` method is called, where you can set up connections and access configuration:

```python
@service()
class MyService:
    async def configure(self, config_instance=None):
        if config_instance:
            self.config = config_instance
```

Use `@after_config` hook to run code after configuration:

```python
from canary_framework import after_config

@service()
class Database:
    @after_config
    async def connect(self):
        self.connection = await connect_to_db(self.config.db_url)
```

### 3. Initialization

The `init()` method is called after all services are configured:

```python
@service()
class MyService:
    async def init(self):
        pass
```

Use `@after_init` hook to run code after initialization:

```python
from canary_framework import after_init

@service()
class UserService:
    @after_init
    async def seed_default_users(self):
        if not await self.db.has_users():
            await self.db.create_default_users()
```

### 4. Startup

The `startup()` method is called when the application is ready to start:

```python
@service()
class MyService:
    async def startup(self):
        pass
```

Use `@before_startup` hook to run code before startup:

```python
from canary_framework import before_startup

@service()
class Server:
    @before_startup
    async def verify_connections(self):
        assert self.db.connection is not None
        assert self.cache.connection is not None
```

### 5. Shutdown

The `shutdown()` method is called when the application is stopping:

```python
@service()
class MyService:
    async def shutdown(self):
        pass
```

Use `@before_shutdown` hook to run code before shutdown:

```python
from canary_framework import before_shutdown

@service()
class Database:
    @before_shutdown
    async def disconnect(self):
        await self.connection.close()
```

## Lifecycle Hooks

Four decorators are available for hooking into the lifecycle:

| Decorator | Phase | Timing |
|-----------|-------|--------|
| `@after_config` | Configuration | After `configure()` is called |
| `@after_init` | Initialization | After `init()` is called |
| `@before_startup` | Startup | Before `startup()` is called |
| `@before_shutdown` | Shutdown | Before `shutdown()` is called |

## Hook Methods

Hooks can be either synchronous or asynchronous:

```python
@service()
class MyService:
    @after_config
    def sync_hook(self):
        print("Configured")

    @after_init
    async def async_hook(self):
        await some_async_operation()
```

## Module Lifecycle

Modules coordinate the lifecycle of their child services:

```python
@module(services=[ServiceA, ServiceB])
class App:
    pass

app = App()

# Configure all services in dependency order
await app.configure(config)

# Initialize all services
await app.init()

# Start all services
await app.startup()

# ... run app ...

# Shutdown all services in reverse order
await app.shutdown()
```

The execution order follows topological sort:
- **Configure**: dependencies first (A → B)
- **Init**: dependencies first (A → B)
- **Startup**: dependencies first (A → B)
- **Shutdown**: reverse order (B → A)

## Complete Lifecycle Example

```python
from canary_framework import (
    service, module,
    after_config, after_init, before_startup, before_shutdown
)

calls = []

@service()
class A:
    @after_config
    def config_a(self):
        calls.append("A: after_config")

    @after_init
    def init_a(self):
        calls.append("A: after_init")

    @before_startup
    def startup_a(self):
        calls.append("A: before_startup")

    @before_shutdown
    def shutdown_a(self):
        calls.append("A: before_shutdown")

@service()
class B:
    a: A  # B depends on A

    @after_config
    def config_b(self):
        calls.append("B: after_config")

    @after_init
    def init_b(self):
        calls.append("B: after_init")

    @before_startup
    def startup_b(self):
        calls.append("B: before_startup")

    @before_shutdown
    def shutdown_b(self):
        calls.append("B: before_shutdown")

@module(services=[A, B])
class App:
    pass

# Run lifecycle
app = App()
await app.configure(config)
await app.init()
await app.startup()
await app.shutdown()

# Resulting order:
# A: after_config
# B: after_config
# A: after_init
# B: after_init
# A: before_startup
# B: before_startup
# B: before_shutdown
# A: before_shutdown
```

## ASGI Lifecycle

When running as an ASGI application, the framework automatically handles the lifecycle:

```python
import uvicorn

@module(services=[...])
class App:
    pass

uvicorn.run("main:App", lifespan="on")
```

The ASGI lifespan protocol will:
1. Call `startup()` when the server starts
2. Call `shutdown()` when the server stops

## Configuration

Pass configuration during the configure phase:

```python
class AppConfig:
    def __init__(self):
        self.database_url = "sqlite:///mydb.db"
        self.debug = True

@service()
class Database:
    @after_config
    async def connect(self):
        url = self.config.database_url
        self.connection = await connect(url)

app = App()
await app.configure(AppConfig())
```

### Logging Configuration

The framework automatically configures logging during `configure()`. No manual
`logging.basicConfig()` is needed.

**Default behavior**: When you call `app.configure(config)`, the framework adds a
`StreamHandler` to the `cf` logger with `INFO` level:

```python
from canary_framework import module

@module(services=[...])
class App:
    pass

class AppConfig:
    def __init__(self):
        self.database_url = "sqlite:///mydb.db"

app = App()
await app.configure(AppConfig())
# Framework logs now visible on stdout:
# [2026-06-02 13:00:00] cf.module             INFO     Configuring module: AppModule
```

**Custom log level**: Set `cf_log_level` on your config object to control the
framework log level:

```python
class AppConfig:
    cf_log_level: str = "DEBUG"  # Show debug-level framework logs
    # ... other config fields ...
```

Valid levels: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`.

**Manual handler**: If you have already configured a handler on the root logger
or the `cf` logger, the framework skips its own setup.

## Error Handling

If a hook raises an exception, it's wrapped in `LifecycleHookError`:

```python
from canary_framework.common import LifecycleHookError

try:
    await app.configure(config)
except LifecycleHookError as e:
    print(f"Lifecycle error: {e}")
```

## Best Practices

1. **Use `@after_config` for connections**: Establish connections after configuration
2. **Use `@after_init` for data setup**: Set up initial data after dependencies are ready
3. **Use `@before_startup` for validation**: Verify everything is ready before serving
4. **Use `@before_shutdown` for cleanup**: Gracefully close connections and save state
5. **Keep hooks focused**: Each hook should do one thing well
6. **Handle errors gracefully**: Catch and log exceptions in hooks
