# Lifecycle

Every service and module supports three lifecycle hooks, all optional. Hooks are defined by the `LifecycleHook` enum and must be explicitly decorated — the framework never auto-detects by method name.

```
Canary.init()  → on_init()  → ...    (topological order: deps first)
Canary.start() → on_start() → ...    (topological order)
Canary.stop()  ← on_end() ← ...      (reverse order: dependants first)
```

## Execution Order

- **`on_init`** and **`on_start`**: topological order — services with no dependencies initialize and start first; dependants follow.
- **`on_end`**: reverse topological order — dependants stop first, then their dependencies.

## `on_init()`

Called during `Canary.init()`. At this point all dependencies **and config** are already injected as instance attributes. The hook receives **no parameters** — everything is on `self`.

```python
@service(name="db", deps=[CacheService], config=AppConfig)
class DBService:
    app_config: AppConfig
    cache_service: CacheService

    @on_init
    def init(self) -> None:
        self.pool = create_pool(self.app_config.dsn)
```

## `on_start()`

Called during `Canary.start()` in topological order. Use for opening connections, registering signal handlers, or starting background tasks.

```python
@on_start
async def start(self) -> None:
    await self.pool.connect()
    self._task = asyncio.create_task(self._loop())
```

## `on_end()`

Called during `Canary.stop()` in **reverse** order. Use for graceful cleanup — closing connections, cancelling tasks, flushing buffers.

```python
@on_end
async def stop(self) -> None:
    self._task.cancel()
    await self.pool.close()
```

## Sync and Async

Hook methods can be `def` or `async def`. The framework detects coroutines via `asyncio.iscoroutine()` and awaits them automatically. You can mix sync and async hooks within the same class.

## LifecycleHook Enum

```python
from canary_framework import LifecycleHook

# LifecycleHook.INIT   == "on_init"
# LifecycleHook.START  == "on_start"
# LifecycleHook.END    == "on_end"
```

## Error Handling

If a hook method raises an exception, the framework wraps it in `LifecycleHookError`:

```python
from canary_framework import LifecycleHookError

try:
    await app.init()
except LifecycleHookError as e:
    print(f"Hook failed: {e}")
```

The original exception is preserved as the `__cause__`, so full tracebacks are available for debugging.

## Phase Overview

```
Canary.init()
    │
    ├── _collect(target)          Phase 0: recursively discover @service / @module / @router
    ├── _validate()               Phase 1: check all deps references exist
    ├── topological_sort()        Phase 2: Kahn BFS — compute safe startup order
    └── for each in startup_order:    Phase 3: per-entry init
        ├── inject_deps()          setattr dependencies on instance
        ├── config_cls()            instantiate config, setattr on instance
        └── @on_init()              hook callback (no arguments)

Canary.start()
    └── for each in startup_order: @on_start() (topological order)

Canary.stop()
    └── for each in reversed:       @on_end() (reverse order)
```
