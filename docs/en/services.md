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
from canary_framework import service, on_init, on_end

@service(
    name="UserService",
    config=AppConfig,           # optional: @config-decorated class
    deps=[DBService],           # optional: dependency list
)
class UserService:
    app_config: AppConfig       # type annotation for IDE support
    db_service: DBService

    @on_init
    def init(self) -> None:
        self.pool = create_pool(self.app_config.dsn)

    @on_end
    async def stop(self) -> None:
        await self.pool.close()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Globally unique service name |
| `config` | `type \| None` | `None` | `@config`-decorated class; inherits from parent module when `None` |
| `deps` | `list[type] \| None` | `None` | Dependency classes injected as `self.<snake_case>` attributes |

## Naming Convention

Dependencies and config are injected as instance attributes using the **snake_case** version of the class name:

| Class | Injected As |
|-------|-------------|
| `DBService` | `self.db_service` |
| `CacheService` | `self.cache_service` |
| `AppConfig` | `self.app_config` |
| `DataSetAdminService` | `self.data_set_admin_service` |

Type annotations (`app_config: AppConfig`) are optional but recommended for IDE support.

## Lifecycle Hooks

Hooks must be explicitly marked with decorators. The framework does **not** auto-detect by method name.

```python
from canary_framework import LifecycleHook

# LifecycleHook.INIT   → @on_init    (topological order, no parameters)
# LifecycleHook.START  → @on_start   (topological order)
# LifecycleHook.END    → @on_end     (reverse order)
```

Hook methods can be sync (`def`) or async (`async def`) — the framework adapts automatically.


