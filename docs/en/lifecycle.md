# Lifecycle

Every service and module supports four lifecycle hooks, all optional. Hooks are defined by the `LifecycleHook` enum and must be explicitly decorated — the framework never auto-detects by method name.

```
Canary.config() → on_config() → ...   (wiring + config injection, topological order)
Canary.init()   → on_init()   → ...   (topological order: deps first)
Canary.start()  → on_start()  → ...   (topological order)
Canary.stop()   ← on_end()  ← ...     (reverse order: dependants first)
```

## Execution Order

- **`on_config`**, **`on_init`**, and **`on_start`**: topological order — services with no dependencies run first; dependants follow.
- **`on_end`**: reverse topological order — dependants stop first, then their dependencies.

## `on_config()`

Called during `Canary.config()`. At this point wiring is complete — dependencies are injected as instance attributes, and config model fields matching the service name are available. The hook receives **no parameters** — everything is on `self`.

```python
@service(name="db", deps=[CacheService])
class DBService:
    cache_service: CacheService

    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.pool_size, self.timeout)
        # pool_size and timeout injected from DBConfig field in the app config model
```

## `on_init()`

Called during `Canary.init()`. At this point all dependencies are injected as instance attributes. Config fields are already available from the `on_config` phase. The hook receives **no parameters** — everything is on `self`.

```python
@service(name="db", deps=[CacheService])
class DBService:
    cache_service: CacheService

    @on_init
    def init(self) -> None:
        self.pool.ping()
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

# LifecycleHook.CONFIG == "on_config"
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
Canary.config(config=Model())
    │
    ├── _collect(target)          Phase 0: recursively discover @service / @module / @router
    ├── _validate()               Phase 1: check all deps references exist
    ├── topological_sort()        Phase 2: Kahn BFS — compute safe startup order
    └── for each in startup_order:    Phase 3: wiring + on_config
        ├── inject_deps()          setattr dependencies on instance
        ├── inject_config()         setattr config fields on instance
        └── @on_config()            hook callback (no arguments)

Canary.init()
    └── for each in startup_order: @on_init() (topological order)

Canary.start()
    └── for each in startup_order: @on_start() (topological order)

Canary.stop()
    └── for each in reversed:       @on_end() (reverse order)
```
