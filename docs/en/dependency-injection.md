# Dependency Injection

Dependencies are declared in the `deps` list and injected as instance attributes **before** `on_init` runs. Dependency attributes use the **snake_case** form of the class name.

## Basic Usage

```python
@service(name="A")
class A:
    def work(self) -> str:
        return "done"

@service(name="B", deps=[A])
class B:
    a: A

    @on_init
    def init(self) -> None:
        result = self.a.work()     # A is already injected
```

## Naming Convention

The attribute name is derived from the class name via `to_snake()`:

| Dependency Class | Injected As |
|------------------|-------------|
| `DBService` | `self.db_service` |
| `UserService` | `self.user_service` |
| `CacheService` | `self.cache_service` |
| `DataSetAdminService` | `self.data_set_admin_service` |
| `HTTPSConnection` | `self.https_connection` |

## Injection Timing

```
Instantiation → Dependency Injection → Config Loading → on_init()
```

All injected dependencies **and** config are available in `on_init`. The hook receives no arguments — everything is already on `self`.

## Config as Dependency Injection

Config classes are injected the same way — using `to_snake` of the config class name:

```python
@service(name="db", config=AppConfig)
class DBService:
    app_config: AppConfig          # injected before on_init

    @on_init
    def init(self) -> None:
        self.pool = connect(self.app_config.dsn)
```

## Cross-Module Dependencies

Services can depend on services declared in parent, sibling, or child modules as long as all classes are reachable from the root module:

```python
@module(name="ModuleA", services=[SvcA])
class ModuleA:
    pass

@module(name="ModuleB", services=[SvcB])
class ModuleB:
    pass

@service(name="SvcA")
class SvcA:
    pass

@service(name="SvcB", deps=[SvcA])   # cross-module dependency
class SvcB:
    svc_a: SvcA
```

## Modules and Routers as Dependencies

Since `@module` and `@router` internally call `@service`, they can be declared as dependencies:

```python
@router(prefix="/data", deps=[DBService])
class DataRouter:
    db_service: DBService

@module(name="App", deps=[DataRouter], services=[DBService])
class App:
    data_router: DataRouter
```

## Startup Order

The framework uses **Kahn's algorithm** (BFS) for topological sorting. Services with no dependencies start first; dependants follow. The computed order guarantees that every dependency is initialized before its dependant.

## Circular Dependencies

Circular dependencies are detected during topological sort and raise `CircularDependencyError`:

```python
from canary_framework import CircularDependencyError

try:
    await app.init()
except CircularDependencyError as e:
    print(f"Cycle detected: {e}")
```

## Missing Dependencies

If a `deps` entry points to a class that is not registered, init raises a `ValueError` during the validation phase with the list of all registered names:

```
ValueError: Service 'B' depends on 'C', but 'C' is not registered.
            Registered names: ['A', 'B']
```

At runtime, if a dependency instance is `None` (which should not happen under normal operation), `DependencyInjectionError` is raised.
