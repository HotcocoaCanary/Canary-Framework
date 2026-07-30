# Lifecycle

Every node has one explicit state machine:

`CREATED → INITIALIZED → STARTED → STOPPED`; failures enter `FAILED`.

```python
@service()
class Database(ServiceBase):
    async def on_init(self) -> None:
        self.pool: Pool | None = None

    async def on_startup(self) -> None:
        self.pool = await create_pool()

    async def on_shutdown(self) -> None:
        if self.pool is not None:
            await self.pool.close()
```

- `on_init`: structural, deterministic setup that does not require a running event loop resource.
- `on_startup`: event-loop-bound, long-lived resources.
- `on_shutdown`: graceful cleanup.

All extensions must be async. Public `init`, `startup`, and `shutdown` reject illegal repeats and must not be overridden. `await app.init()` is mandatory before serving. ASGI lifespan only calls startup and shutdown; it rejects an uninitialized root.

Dependencies initialize/start before consumers and stop in reverse order. On failure, the engine performs private idempotent rollback and preserves `FAILED`; these rollback methods are implementation details, not public API.
