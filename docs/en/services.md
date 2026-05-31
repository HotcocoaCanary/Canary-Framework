# Services

Services are the building blocks of your Canary Framework application. They encapsulate business logic and can be composed together to form complex systems.

## Defining a Service

Use the `@service` decorator to define a service:

```python
from canary_framework import service

@service(name="user_repository")
class UserRepository:
    def __init__(self):
        self.users = []
    
    async def get_all(self):
        return self.users
    
    async def add(self, user):
        self.users.append(user)
        return user
```

### Service Parameters

- `name`: (required) A unique identifier for the service
- `deps`: (optional) A list of service classes this service depends on

## Service Dependencies

Services can depend on other services. Declare dependencies using the `deps` parameter:

```python
@service(name="database")
class DatabaseService:
    pass

@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        # The database service is automatically injected
        # as self.database_service
        return await self.database_service.query(...)
```

Dependencies are automatically injected as attributes in snake_case format:
- `DatabaseService` → `self.database_service`
- `UserRepository` → `self.user_repository`

## Service Lifecycle

Services go through a well-defined lifecycle:

1. **Instantiation**: Service instance is created
2. **Configuration**: `configure()` method is called
3. **Initialization**: `init()` method is called
4. **Startup**: `startup()` method is called
5. **Shutdown**: `shutdown()` method is called (when the application stops)

You can hook into these phases using lifecycle decorators. See the [Lifecycle](./lifecycle.md) documentation for details.

## Service Base Class

When you decorate a class with `@service`, it automatically inherits from `ServiceBase`, which provides:

- `config` attribute: Access to configuration passed during configure phase
- `configure(config)` method: Configures the service
- `init()` method: Initializes the service
- `startup()` method: Starts the service
- `shutdown()` method: Shuts down the service

## Complete Example

```python
from canary_framework import service, after_config, after_init, before_startup, before_shutdown

@service(name="cache")
class CacheService:
    def __init__(self):
        self.cache = {}
        self.connection = None
    
    @after_config
    async def connect(self):
        # Connect to cache server
        self.connection = "connected"
        print("Cache connected")
    
    @after_init
    async def warmup(self):
        # Pre-populate cache with common data
        self.cache["default"] = {"value": "default"}
        print("Cache warmed up")
    
    @before_startup
    async def verify(self):
        # Verify cache is ready
        assert self.connection is not None
        print("Cache verified")
    
    @before_shutdown
    async def cleanup(self):
        # Cleanup resources
        self.connection = None
        print("Cache disconnected")
    
    async def get(self, key):
        return self.cache.get(key)
    
    async def set(self, key, value):
        self.cache[key] = value
```

## Testing Services

Services are easy to test because they're plain Python classes:

```python
import pytest

@pytest.mark.asyncio
async def test_cache_service():
    service = CacheService()
    await service.configure()
    await service.init()
    await service.startup()
    
    await service.set("key", "value")
    assert await service.get("key") == "value"
    
    await service.shutdown()
```
