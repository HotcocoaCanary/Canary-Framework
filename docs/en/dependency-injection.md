# Dependency Injection

Canary Framework has a built-in dependency injection (DI) system that manages service dependencies automatically.

## How It Works

1. **Declare dependencies**: Specify which services a service depends on
2. **Register services**: Services are registered in a registry
3. **Topological sort**: Services are sorted in dependency order
4. **Instantiate and inject**: Services are instantiated and dependencies are injected

## Declaring Dependencies

Use the `deps` parameter to declare dependencies:

```python
@service(name="database")
class DatabaseService:
    pass

@service(name="cache")
class CacheService:
    pass

@service(name="user_repository", deps=[DatabaseService, CacheService])
class UserRepository:
    # DatabaseService is available as self.database_service
    # CacheService is available as self.cache_service
    pass
```

## Injection Naming

Dependencies are injected as attributes using snake_case naming:

| Class Name | Attribute Name |
|------------|----------------|
| `DatabaseService` | `self.database_service` |
| `UserRepository` | `self.user_repository` |
| `APIRouter` | `self.api_router` |

## Dependency Graph

The framework builds a dependency graph and ensures services are initialized in the correct order:

```python
@service(name="a")
class A:
    pass

@service(name="b", deps=[A])
class B:
    pass

@service(name="c", deps=[B])
class C:
    pass

# Startup order: A → B → C
```

## Circular Dependencies

The framework detects and reports circular dependencies:

```python
# ❌ This will throw CircularDependencyError
@service(name="a", deps=["b"])
class A:
    pass

@service(name="b", deps=["a"])
class B:
    pass
```

## Shared Instances

Services are singletons within their module - only one instance is created and shared:

```python
@service(name="database")
class DatabaseService:
    def __init__(self):
        print("DatabaseService created")  # Only printed once

@service(name="service1", deps=[DatabaseService])
class Service1:
    pass

@service(name="service2", deps=[DatabaseService])
class Service2:
    pass

@module(name="app", services=[DatabaseService, Service1, Service2])
class AppModule:
    pass

# Both Service1 and Service2 get the same DatabaseService instance
```

## Parent Registry

Modules can have parent registries, allowing services to be shared across modules:

```python
@service(name="shared_db")
class SharedDatabase:
    pass

@service(name="auth_service", deps=[SharedDatabase])
class AuthService:
    pass

@service(name="product_service", deps=[SharedDatabase])
class ProductService:
    pass

@module(name="auth", services=[AuthService])
class AuthModule:
    pass

@module(name="products", services=[ProductService])
class ProductsModule:
    pass

@module(name="app", services=[SharedDatabase, AuthModule, ProductsModule])
class AppModule:
    pass

# Both AuthService and ProductService share the same SharedDatabase instance
```

## Manual Injection

You can manually inject dependencies if needed:

```python
from canary_framework.engine.registry import Registry
from canary_framework.engine.injector import inject_deps

# Create registry
registry = Registry()
registry.register(MyService)
registry.register(MyDependency)

# Create instances
for entry in registry:
    entry.instance = entry.cls()

# Inject dependencies
for entry in registry:
    inject_deps(entry.instance, entry, registry)
```

## Service Registry

The `Registry` class manages service registration and lookup:

```python
from canary_framework.engine.registry import Registry

registry = Registry()

# Register a service
registry.register(MyService)

# Lookup by name
entry = registry.get_by_name("my_service")

# Lookup by class
entry = registry.get_by_class(MyService)

# Check if registered
if MyService in registry:
    pass

# Get all services
for entry in registry:
    print(entry.name)
```

## ServiceEntry

Each service in the registry is represented by a `ServiceEntry`:

```python
@dataclass
class ServiceEntry:
    cls: type              # The service class
    name: str              # Service name
    instance: object       # Service instance (None until configured)
    deps: list[type]       # Dependencies
    dep_names: list[str]   # Dependency names
```

## Topological Sort

The framework uses Kahn's algorithm for topological sorting:

```python
from canary_framework.engine.injector import topological_sort

# Get the startup order
order = topological_sort(registry)
# Returns: ["a", "b", "c"]
```

## Complete DI Example

```python
from canary_framework import module, service

# Layer 1: Infrastructure
@service(name="database")
class DatabaseService:
    async def query(self, sql):
        return f"Query: {sql}"

@service(name="cache")
class CacheService:
    async def get(self, key):
        return None
    
    async def set(self, key, value):
        pass

# Layer 2: Repositories
@service(name="user_repo", deps=[DatabaseService, CacheService])
class UserRepository:
    async def get_user(self, user_id):
        cached = await self.cache_service.get(f"user:{user_id}")
        if cached:
            return cached
        
        user = await self.database_service.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache_service.set(f"user:{user_id}", user)
        return user

# Layer 3: Services
@service(name="user_service", deps=[UserRepository])
class UserService:
    async def get_profile(self, user_id):
        user = await self.user_repo.get_user(user_id)
        return {"profile": user}

# Layer 4: Composition
@module(name="app", services=[DatabaseService, CacheService, UserRepository, UserService])
class AppModule:
    pass
```

## Design Principles

1. **Explicit dependencies**: Dependencies are declared clearly
2. **Constructor injection**: No magic, dependencies are set as attributes
3. **Topological order**: Services start in the right order
4. **Single instances**: Services are singletons within their scope
5. **Error detection**: Circular dependencies are caught early
