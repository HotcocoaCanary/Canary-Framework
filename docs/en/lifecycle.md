# Lifecycle

Three optional hook stages.

```
Canary.init()  → on_init(ctx) → ...   (topological order)
Canary.start() → on_start() → ...     (topological order)
Canary.stop()  ← on_end() ← ...       (reverse order)
```

## `on_init(ctx)`

Receives Context. Dependencies injected, config loaded:

```python
@on_init
def init(self, ctx: Context):
    self.pool = create_pool(ctx.config.db_url)
```

## `on_start()`

```python
@on_start
async def start(self):
    await self.pool.connect()
```

## `on_end()`

```python
@on_end
def end(self):
    self.pool.close()
```

Hooks can be `async def` — the framework automatically detects and `await`s them.
