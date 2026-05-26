# Dependency Injection

## Minimal: declare dependencies

```python
@service(name="B", deps=[A])
class B:
    def work(self) -> str:
        return self.a.do()            # A auto-injected as self.a
```

## Injection Rules

ClassName → snake_case → attribute name:

| Dependency Class | Injected As |
|------------------|-------------|
| `DBService` | `self.db_service` |
| `UserService` | `self.user_service` |
| `DataSetAdminService` | `self.data_set_admin_service` |

## Injection Timing

```
Instantiation → Dependency Injection → Config Loading → on_init(ctx)
```

All injected dependencies are available in `on_init`.

## Startup Order

Kahn topological sort: dependencies start before dependents, dependency-free services start first. Circular dependencies raise `CircularDependencyError`:

```python
from canary_framework import CircularDependencyError

try:
    await app.init()
except CircularDependencyError as e:
    print(f"Cycle detected: {e}")
```

## Type-Safe Resolution

In addition to dependency injection, you can manually resolve services via Context:

```python
@on_init
def init(self, ctx: Context) -> None:
    db = ctx.get_service(DBService)   # type-safe service lookup
    db.execute("SELECT 1")
```

If the service is not found, a `ServiceNotFoundError` is raised.
