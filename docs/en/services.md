# Services

## Minimal

```python
from canary_framework import service, on_start, Canary

@service(name="HelloService")
class HelloService:
    @on_start
    def start(self) -> None:
        print("started")
```

- `name`: globally unique, required
- Everything else is optional

## Full

```python
from canary_framework import service, on_init, on_end, Context

@service(
    name="UserService",         # required: globally unique name
    config=UserConfig,          # optional: @config-decorated config class
    deps=[DBService],           # optional: dependency list, auto-injected as self.db_service
)
class UserService:
    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(UserConfig)  # type-safe config access
        self.db_service.query()          # use injected dependency

    @on_start
    async def start(self) -> None:
        await self.pool.connect()

    @on_end
    def end(self) -> None:
        self.pool.close()
```

## Lifecycle Hooks

Hooks must be explicitly marked with decorators. The framework does not auto-detect by method name:

```python
from canary_framework import LifecycleHook

# LifecycleHook.INIT   → @on_init    (topological order, receives Context)
# LifecycleHook.START  → @on_start   (topological order, no args)
# LifecycleHook.END    → @on_end     (reverse order, no args)
```

Hook methods can be sync (`def`) or async (`async def`). The framework adapts automatically.
