# Lifecycle

Three hook stages, all optional. Hook names are defined by the `LifecycleHook` enum and must be explicitly decorated with `@on_init` / `@on_start` / `@on_end`.

```
Canary.init()  → on_init(ctx) → ...   (topological order)
Canary.start() → on_start() → ...     (topological order)
Canary.stop()  ← on_end() ← ...       (reverse order)
```

## `on_init(ctx)`

Receives Context. At this point, dependencies are injected and config is loaded:

```python
@on_init
def init(self, ctx: Context) -> None:
    cfg = ctx.get_config(AppConfig)
    self.pool = create_pool(cfg.db_url)
```

## `on_start()`

```python
@on_start
async def start(self) -> None:
    await self.pool.connect()
```

## `on_end()`

```python
@on_end
def end(self) -> None:
    self.pool.close()
```

Hooks can be `async def` — the framework automatically detects this via `asyncio.iscoroutine` and `await`s them.

## LifecycleHook Enum

```python
from canary_framework import LifecycleHook

# LifecycleHook.INIT   == "on_init"
# LifecycleHook.START  == "on_start"
# LifecycleHook.END    == "on_end"
```

## Error Handling

If a hook method raises an exception, the framework wraps it in a `LifecycleHookError`:

```python
from canary_framework import LifecycleHookError

try:
    await app.init()
except LifecycleHookError as e:
    print(f"Hook failed: {e}")
```
