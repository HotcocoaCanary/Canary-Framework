# Lifecycle

`Canary` drives every unit through an explicit, async-native timeline.

## Five moments

The framework splits "a unit from nothing to running to gone" into five moments. The criterion
is one thing: **what you have in your hands at that moment.**

| Moment | Who acts | What you have |
|---|---|---|
| Construction | your `__init__` | nothing (no arguments) |
| **Assembly** | **the framework** | build → validate → sort → inject |
| Init `@on_init` | you | dependencies in place, nothing running yet |
| Start `@on_start` | you | dependencies in place; acquire resources |
| Stop `@on_stop` | you | reclaim, in reverse |

The middle step is **a framework action, not a user hook** — which is exactly why it needs no
hook: at any instant during assembly you would have nothing that the moments on either side do
not already give you.

## Three hooks

| Declaration | Runs during | Order |
|---|---|---|
| `@on_init` | `init()`, after injection | topological (dependencies first) |
| `@on_start` | `start()` | topological (dependencies first) |
| `@on_stop` | `stop()` | reverse topological (dependents first) |

All hooks are optional and may be sync or async — the runtime inspects the return value and only
awaits when it is awaitable, so the two mix freely.

## What each method does

| Method | Transition | What it does |
|---|---|---|
| `await app.init()` | `NEW → INITIALIZED` | build, validate, sort, **inject dependencies**, run `@on_init` in order |
| `await app.start()` | `INITIALIZED → STARTED` | run `@on_start` in order |
| `await app.stop()` | any settled state `→ STOPPED` | run `@on_stop` in reverse |

In one line: **`init` assembles the graph so every unit is usable; `start` lets them go to work.**

## The state machine

```
NEW ─▶ INITIALIZING ─▶ INITIALIZED ─▶ STARTING ─▶ STARTED ─▶ STOPPING ─▶ STOPPED
        │                            │                    │
        └───────────────▶ FAILED ◀───┴────────────────────┘
```

`app.state` returns the current `LifecycleState`. Illegal transitions raise `LifecycleError`:

```python
await app.init()
await app.start()
await app.start()  # LifecycleError: illegal transition from STARTED
```

## Hook order

For the graph `APIService → UserService → Database` (arrow = "depends on"):

- **Init** — `Database` → `UserService` → `APIService`
- **Start** — `Database` → `UserService` → `APIService`
- **Stop** — `APIService` → `UserService` → `Database`

Every unit is initialised and started after its dependencies, and stopped before them. The order
comes from Kahn's algorithm, so it is deterministic.

## Hooks stack

One marker can be shared by several methods — mixin hooks run before the class's own, in
definition order:

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

## Failure paths

Failure paths are a deliberate part of this framework, and the three rules differ:

**A failing `init()` does not unwind.** No `@on_start` has run yet, so there is nothing to
reclaim. The state becomes `FAILED` and the exception propagates unchanged.

**A failing `start()` unwinds everything.** The invariant is *either everything started, or
nothing did*. When any step raises, every unit that **entered** `@on_start` (including the one
that failed) runs its `@on_stop` in reverse, and then the original exception is re-raised;
failures during that unwind are attached to it as notes, without changing its type.

**`stop()` is the single reclamation path.** It serves both normal and failed termination:

```python
app = Canary(Root)
try:
    await app.init()
    await app.start()
finally:
    await app.stop()   # callable from STARTED and from FAILED; idempotent
```

Calling `stop()` on something that never started is not an error — it is a no-op that settles
into `STOPPED` (an earlier `FAILED` is not erased). That makes `finally: await app.stop()`
always safe, with no state check first.

A single failing `@on_stop` does not abort the shutdown: errors are collected, the remaining
units are reclaimed anyway, and everything is raised at the end as one `ExceptionGroup`.

## Letting a host drive it

Two host protocols, two entry points:

| What the host takes | Use | Who does this |
|---|---|---|
| an async context manager, `Callable[[Host], AsyncContextManager]` | `canary.lifespan` | ASGI (Starlette / FastAPI / Litestar), MCP, FastStream |
| paired startup / shutdown callbacks | `init()` / `start()` and `stop()` | Quart, Sanic, arq, Dramatiq |

```python
app = FastAPI(lifespan=canary.lifespan)          # that is the whole wiring
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
server = MCPServer("demo", lifespan=canary.lifespan)
```

Without a host (a CLI, a script, a test fixture) use it directly:

```python
async with canary.lifespan():
    ...
```

The framework knows about none of them specifically — the table above covers the only two shapes
that exist in Python.

`canary.lifespan` differs from `async with canary` in exactly one way: **it yields `None` rather
than the container.** The ASGI lifespan protocol treats the yielded value as a mapping to merge
into `scope["state"]`, so yielding the container makes Starlette call `dict.update(canary)` and
leak a `KeyError` with no clue in it. `async with canary` serves your own code and still hands
back the container.

## Two environment variables

The framework has exactly two knobs of its own, read straight from the environment:

| Variable | Effect |
|---|---|
| `CANARY_LOG_LEVEL` | Sets the level of the `canary` logger tree only. No handler, no format, nothing touched on root. `DEBUG` also prints the assembly summary (start order, dependencies, routes). |
| `CANARY_SLOW_CALLBACK_SECONDS` | Turns on an event-loop lag probe: any callback occupying the loop for longer than this gets an asyncio WARNING. It enables asyncio debug mode and costs something, so it is a development tool and off by default. |

The framework provides no configuration mechanism — configuration is just one of your own
`@cocoa` units, and logging is the standard library's `logging.getLogger(__name__)`.
