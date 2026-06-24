# Services

Services are the building blocks of your Canary Framework application. They encapsulate business logic and can be composed together to form complex systems.

## Defining a Service

Use the `@service()` decorator to define a service:

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class UserRepository(ServiceBase):
    def __init__(self):
        self.users = []

    async def get_all(self):
        return self.users

    async def add(self, user):
        self.users.append(user)
        return user
```

- Services are automatically named `ClassName` + `"Service"` — e.g., `UserRepository` → `UserRepositoryService`
- Name is auto-generated from the class name
- To add HTTP routes, define a `router` class attribute with a `Router` instance (see [Routers & HTTP](./web.md))

## Declaring Dependencies

Dependencies are declared via Python type annotations, not a `deps` list:

```python
@service()
class Database(ServiceBase):
    pass

@service()
class UserRepo(ServiceBase):
    db: Database  # Declared via annotation — auto-injected

    async def get_user(self, user_id):
        return await self.db.query(...)
```

- Annotations are resolved by `resolve_deps()` — only types marked with `CF_SERVICE_MARKER` are treated as dependencies
- The injected instance is set on the annotation key name (e.g., `self.db` for `db: Database`)
- **You control the attribute name** — use any valid Python identifier: `db`, `cache`, `repo`, etc.

## Service Lifecycle

Services go through a well-defined lifecycle:

1. **Instantiation**: Service instance is created
2. **Initialization**: `init()` is called; override for connection setup and data seeding
3. **Startup**: `startup()` is called; `async def startup(self):\n        await super().startup()` hooks run before
4. **Shutdown**: `async def shutdown(self):\n        await super().shutdown()` hooks run, then `shutdown()` is called

You can hook into these phases using lifecycle decorators. See the [Lifecycle](./lifecycle.md) documentation for details.

## Service Base Class

Classes decorated with `@service()` must explicitly inherit from `ServiceBase`, which provides:

- `init()` method: Initializes the service
- `startup()` method: Starts the service
- `shutdown()` method: Shuts down the service

## Complete Example

```python
from canary_framework import service, before_startup, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Cache(ServiceBase):
    def __init__(self):
        self.store = {}
        self.connection = None

    async def init(self):
        await super().init()
        self.connection = "connected"
        print("Cache connected")
        self.store["default"] = {"value": "default"}
        print("Cache warmed up")

    async def startup(self):\n        await super().startup()
    async def verify(self):
        assert self.connection is not None
        print("Cache verified")

    async def shutdown(self):\n        await super().shutdown()
    async def cleanup(self):
        self.connection = None
        print("Cache disconnected")

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value
```

## Service Naming

Service names are derived automatically from the class name:

| Class Name | Service Name (auto) |
|------------|---------------------|
| `Database` | `DatabaseService` |
| `UserRepository` | `UserRepositoryService` |
| `Cache` | `CacheService` |

This name is used internally for registry lookups. In most code, you reference services by their class.

## Testing Services

Services are easy to test because they're plain Python classes:

```python
import pytest

@pytest.mark.asyncio
async def test_cache():
    svc = Cache()
    await svc.init()
    await svc.startup()

    await svc.set("key", "value")
    assert await svc.get("key") == "value"

    await svc.shutdown()
```

## Best Practices

1. **Single Responsibility**: Each service should do one thing well
2. **Stateless Design**: Prefer stateless services or manage state explicitly
3. **Minimal Dependencies**: Only declare dependencies you actually need
4. **Type Annotations**: Use type hints for clear dependency declarations
5. **Test Coverage**: Write unit tests for each service
6. **Meaningful Annotation Names**: Choose descriptive names for dependency attributes (e.g., `db` not `d`)
