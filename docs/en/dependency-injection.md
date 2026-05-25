# Dependency Injection

## Minimal: declare dependencies

```python
@service(name="B", deps=[A])
class B:
    def work(self):
        self.a.do()            # A auto-injected as self.a
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
Instantiation → DI → config loading → on_init(ctx)
```

All injected dependencies are available in `on_init`.

## Startup Order

Kahn topological sort: dependencies start before dependents. Circular dependencies raise `RuntimeError`.
