# Lifecycle

`Canary` drives each unit through an explicit, async-native lifecycle. Hooks are declared with
`@on_init` / `@on_start` / `@on_stop` and run in a deterministic order.

## The three hooks

| Declaration | Runs during | Order |
|---|---|---|
| `@on_init` | `init()` | topological (dependencies first) |
| `@on_start` | `start()` | topological (dependencies first), after injection |
| `@on_stop` | `stop()` | reverse topological (dependents first) |

Every hook is optional. A hook may be a plain function or a coroutine function — the runtime
inspects the return value and `await`s it only when it is awaitable, so sync and async hooks mix
freely.

## State machine

Each `Canary` tracks an eight-state machine:

```
NEW ─▶ INITIALIZING ─▶ INITIALIZED ─▶ STARTING ─▶ STARTED ─▶ STOPPING ─▶ STOPPED
        │                            │                    │
        └───────────────▶ FAILED ◀───┴────────────────────┘
```

`app.state` returns the current `LifecycleState`. The state machine guarantees lifecycle
operations run in a legal order:

```python
await app.stop()  # LifecycleError: illegal transition from NEW
await app.init()
await app.start()
await app.start()  # LifecycleError: illegal transition from STARTED
```

A hook that raises marks the state `FAILED` and re-raises the exception.

## Hook ordering

For a graph `APIService → UserService → Database` (arrow = "depends on"):

- **Init** — `Database` → `UserService` → `APIService`.
- **Start** — `Database` → `UserService` → `APIService`.
- **Stop** — `APIService` → `UserService` → `Database`.

Every unit initialises and starts only after its dependencies; it stops before its
dependencies. The order comes from a Kahn topological sort, so it is deterministic.

## Hooks are stacked

A marker can be shared by several methods — mixin hooks run before the class's own, in
definition order. This lets a mixin add `@on_start` behaviour without overriding the class's:

```python
class LoggingMixin:
    @on_start
    def log_start(self) -> None:
        print(f"[{type(self).__name__}] starting")


@cocoa(deps=[Config])
class Database(LoggingMixin):
    @on_start
    async def connect(self) -> None:
        await self.pool.connect()
```

Both `log_start` (mixin) and `connect` (class) run, in that order.

## Failure handling

A hook exception propagates out of `init()` / `start()` / `stop()` after the runtime sets the
state to `FAILED`. The runtime does not attempt automatic rollback — build rollback into your
own `@on_stop` hooks where a partial teardown matters.

## Under an ASGI server

When `Canary` is served through ASGI (e.g. via uvicorn), the `lifespan` protocol drives the
same lifecycle: `lifespan.startup` runs `init()` + `start()`, `lifespan.shutdown` runs
`stop()`. Explicit calls and the server path share one engine.
