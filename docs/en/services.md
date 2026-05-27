# Services

A **service** is the smallest runtime unit in the Canary Framework. Every `@service`-decorated class owns its own lifecycle hooks, dependencies, and optional configuration.

## Minimal

```python
from canary_framework import service, on_start, Canary

@service(name="HelloService")
class HelloService:
    @on_start
    def start(self) -> None:
        print("started")
```

- `name`: globally unique, **required**
- Everything else is optional

## Full

```python
from canary_framework import service, on_config, on_init, on_end

@service(
    name="UserService",
    deps=[DBService],           # optional: dependency list
)
class UserService:
    db_service: DBService

    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.config.dsn)  # config accessible via self.config

    @on_end
    async def stop(self) -> None:
        await self.pool.close()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Globally unique service name |
| `deps` | `list[type] \| None` | `None` | Dependency classes injected as `self.<snake_case>` attributes |

## Naming Convention

Dependencies are injected as instance attributes using the **snake_case** version of the class name:

| Class | Injected As |
|-------|-------------|
| `DBService` | `self.db_service` |
| `CacheService` | `self.cache_service` |
| `DataSetAdminService` | `self.data_set_admin_service` |

The config instance passed to `app.config(config=...)` is available as `self.config` on every service and module in the tree. See [Configuration](./configuration.md).

## Lifecycle Hooks

Hooks must be explicitly marked with decorators. The framework does **not** auto-detect by method name.

```python
from canary_framework import LifecycleHook

# LifecycleHook.CONFIG → @on_config  (topological order, after wiring)
# LifecycleHook.INIT   → @on_init    (topological order, no parameters)
# LifecycleHook.START  → @on_start   (topological order)
# LifecycleHook.END    → @on_end     (reverse order)
```

Hook methods can be sync (`def`) or async (`async def`) — the framework adapts automatically.


