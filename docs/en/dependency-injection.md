# Dependency Injection

Canary Framework has a built-in, annotation-driven dependency injection (DI) system that manages service dependencies automatically.

## How It Works

1. **Declare dependencies**: Use Python type annotations on your service class
2. **Resolve**: `resolve_deps(cls)` reads annotations and filters by `CF_SERVICE_MARKER`
3. **Register**: Services and their dependencies are registered recursively
4. **Topological sort**: `topological_sort(registry)` builds the dependency graph and determines instantiation order
5. **Instantiate and inject**: Services are instantiated in order; dependencies set via `setattr` using the annotation key name

## Declaring Dependencies

Use type annotations on the class body to declare dependencies:

```python
@service()
class Database(ServiceBase):
    pass

@service()
class Cache(ServiceBase):
    pass

@service()
class UserRepository(ServiceBase):
    db: Database    # Auto-injected as self.db
    cache: Cache    # Auto-injected as self.cache

    async def get_user(self, user_id):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        user = await self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache.set(f"user:{user_id}", user)
        return user
```

The annotation key name becomes the attribute name on the instance:

| Annotation | Injected As |
|------------|-------------|
| `db: Database` | `self.db` |
| `cache: Cache` | `self.cache` |
| `auth: AuthService` | `self.auth` |

**You choose the attribute name** — simply name the annotation field however you want.

## Dependency Graph

The framework builds a dependency graph and ensures services are initialized in the correct order:

```python
@service()
class A(ServiceBase):
    pass

@service()
class B(ServiceBase):
    a: A  # Depends on A

@service()
class C(ServiceBase):
    b: B  # Depends on B

# Topological sort determines order: A → B → C
```

## DI Execution Flow

```
1. resolve_deps(cls) reads annotations on the class
   ↓
2. Filter annotations: keep only types with CF_SERVICE_MARKER
   ↓
3. Register each dependency recursively in the registry
   ↓
4. topological_sort(registry) builds dependency graph
   ↓
5. Instantiate services in topological order
   ↓
6. For each service: setattr(instance, attr_name, resolved_dep_instance)
   ↓
7. Run lifecycle hooks
```

## Circular Dependencies

The framework detects and reports circular dependencies:

```python
# ❌ This will throw CircularDependencyError
@service()
class A(ServiceBase):
    b: B

@service()
class B(ServiceBase):
    a: A
```

## Shared Instances

Services are singletons within their module — only one instance is created and shared:

```python
@service()
class Database(ServiceBase):
    def __init__(self):
        print("Database created")  # Only printed once

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

## Parent Registry

Modules can have parent registries, allowing services to be shared across modules:

```python
@service()
class SharedDatabase(ServiceBase):
    pass

@service()
class AuthService(ServiceBase):
    db: SharedDatabase

@service()
class ProductService(ServiceBase):
    db: SharedDatabase

@module(services=[AuthService])
class AuthModule(ModuleBase):
    pass

@module(services=[ProductService])
class ProductsModule(ModuleBase):
    pass

@module(services=[SharedDatabase, AuthModule, ProductsModule])
class App(ModuleBase):
    pass

# Both AuthService and ProductService share the same SharedDatabase instance
```

## Module Children Access

Module child services are accessible as attributes using the class name:

```python
@module(services=[Database, Auth])
class App(ModuleBase):
    pass

app = App()
await app.init()  # Config auto-discovered from services list

# Access children directly by class name
app.Database    # Database service instance
app.Auth        # Auth service instance
```

## Manual Injection

You can manually resolve dependencies if needed:

```python
from canary_framework.engine.registry import Registry
from canary_framework.engine.injector import topological_sort, resolve_deps

registry = Registry()
registry.register(MyService)

# resolve_deps reads annotations on MyService to find deps
# topological_sort uses resolve_deps() to build the full graph
for entry in topological_sort(registry):
    entry.instance = entry.cls()
    # Set dependencies via setattr using annotation key names
```

## Service Registry

The `Registry` class manages service registration and lookup:

```python
from canary_framework.engine.registry import Registry

registry = Registry()

registry.register(MyService)

entry = registry.get_by_class(MyService)

if MyService in registry:
    pass

for entry in registry:
    print(entry.cls)
```

## ServiceEntry

Each service in the registry is represented by a `ServiceEntry`:

```python
@dataclass
class ServiceEntry:
    cls: type                  # The service class
    name: str                  # Auto-generated service name
    instance: object = None    # Service instance (None until configured)
```

## Topological Sort

The framework uses Kahn's algorithm for topological sorting, driven by `resolve_deps()`:

```python
from canary_framework.engine.injector import topological_sort

order = topological_sort(registry)
# Returns entries in dependency order
```

## Complete DI Example

```python
from canary_framework import module, service
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase

# Layer 1: Infrastructure
@service()
class Database(ServiceBase):
    async def query(self, sql):
        return f"Query: {sql}"

@service()
class Cache(ServiceBase):
    async def get(self, key):
        return None

    async def set(self, key, value):
        pass

# Layer 2: Repositories
@service()
class UserRepo(ServiceBase):
    db: Database
    cache: Cache

    async def get_user(self, user_id):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        user = await self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache.set(f"user:{user_id}", user)
        return user

# Layer 3: Services
@service()
class UserService(ServiceBase):
    repo: UserRepo

    async def get_profile(self, user_id):
        user = await self.repo.get_user(user_id)
        return {"profile": user}

# Layer 4: Composition
@module(services=[Database, Cache, UserRepo, UserService])
class App(ModuleBase):
    pass
```

## Design Principles

1. **Annotation-driven**: Dependencies declared with Python type hints — no separate `deps` lists
2. **Flexible naming**: You control the attribute name via the annotation key
3. **Automatic resolution**: `resolve_deps()` discovers dependencies by reading annotations
4. **Topological order**: Services start in the right dependency order
5. **Single instances**: Services are singletons within their scope
6. **Error detection**: Circular dependencies are caught early
