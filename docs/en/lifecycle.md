# Lifecycle

`Canary` drives every unit through an explicit, async-native timeline.

## Five moments

A unit goes from nothing to running to gone through five moments, differing in **what you have
in your hands at that moment**:

| Moment | Who acts | What you have |
|---|---|---|
| Construction | your `__init__` | nothing (no arguments) |
| **Assembly** | **the framework**, inside `Canary(...)` | build → validate → sort → inject |
| Init `@on_init` | you | dependencies in place, nothing running yet |
| Start `@on_start` | you | dependencies in place; acquire resources |
| Stop `@on_stop` | you | reclaim, in reverse |

The middle step is a framework action, not a user hook: it completes synchronously inside
`Canary(...)`, with no point at which user code could run.

## Three hooks

| Declaration | Runs during | Order |
|---|---|---|
| `@on_init` | `init()`, after injection | topological (dependencies first) |
| `@on_start` | `start()` | topological (dependencies first) |
| `@on_stop` | `stop()` | reverse topological (dependents first) |

All hooks are optional and may be sync or async — the runtime inspects the return value and only
awaits when it is awaitable, so the two mix freely.

## What each method does

| When | Transition | What it does |
|---|---|---|
| `Canary(*roots)` | — `→ READY` | assembly: build, validate, sort, **inject dependencies**. Synchronous; runs no hooks |
| `await app.init()` | `READY → INITIALIZED` | settle in: every `@on_init` |
| `await app.start()` | `INITIALIZED → STARTED` | go to work: every `@on_start`, ledgered on entry |
| `await app.stop()` | any settled state `→ STOPPED` | run `@on_stop` in reverse |

Four actions, four meanings, one-to-one: **construction assembles, `init` settles in, `start` goes
to work, `stop` reclaims.** No method does two things. Between `init()` and `start()` there is a
barrier — the whole graph settles before any unit goes to work — and that barrier *is* the method
boundary: until you call `start()`, nothing goes to work.

## The state machine

```
READY ─▶ INITIALIZING ─▶ INITIALIZED ─▶ STARTING ─▶ STARTED ─▶ STOPPING ─▶ STOPPED
             │                            │                       │
             └──────────────▶ FAILED ◀────┴───────────────────────┘
```

Each action has an in-progress state (`*ING`) that only a concurrent caller can ever observe.

It starts at `READY`, not at "nothing has happened yet": assembly is done in the constructor, so
a freshly built runtime is **already usable** — `canary[SomeUnit]` hands back an instance with
its dependencies injected; nothing is running yet, that is all.

`app.state` returns the current `LifecycleState`. Illegal transitions raise `LifecycleError`:

```python
await app.init()
await app.start()
await app.init()
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

**There is one rule: `stop()` reclaims whatever is in the ledger.** When `init()` fails the ledger
is empty (`@on_init` acquires nothing by contract), so there is nothing to reclaim and the state
simply becomes `FAILED`.

The ledger records the units that **entered** `@on_start`. By contract that is the only place
resources are acquired, so it is the only thing that needs reclaiming.

When `start()` fails the invariant is *either everything started, or nothing did*: every unit in
the ledger (including the one that failed) runs its `@on_stop` in reverse, and then the original
exception is re-raised, with any unwind failures attached to it as notes.

A failure during the `@on_init` pass leaves the ledger empty, so the unwind is a no-op — no
separate rule needed for it.

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

## Concurrent startup

```python
Canary(Root, start_concurrency=8)
```

The default, `None`, starts units strictly one at a time in topological order. A positive integer
lets **independent units start together**, at most that many at once. The speed-up is the
sequential total divided by the critical path (the longest dependency chain by time) — entirely a
property of the graph's shape:

```
50 independent 60ms IO units            3009ms → 423ms     7.1x
a typical web shape (DB / Redis / MQ)    260ms → 152ms     1.7x
a single chain                           unchanged          1.0x
```

**Off by default**, for two reasons: concurrent startup opens N connections to a backend at once
(a connection storm — measured: 20 units against a backend that accepts 8 got 12 rejections and a
failed startup), and it breaks "siblings start in declaration order", which was never promised but
may be relied upon.

**The limit is not optional.** The semaphore wraps only the hook execution, not the waiting for
dependencies. Scheduling is dependency-driven — each unit waits for its own dependencies rather
than for a whole topological layer (layering makes a unit wait for the slowest sibling it has
nothing to do with).

**Failure semantics match sequential startup.** When one unit fails its siblings are cancelled; a
cancelled unit may hold half a resource, so it is ledgered and reclaimed like any other. A single
real failure is re-raised as-is (`except RuntimeError` still works); only when several units fail
at once is an `ExceptionGroup` raised, hiding none of them.

**The framework suggests a value.** With `CANARY_LOG_LEVEL=DEBUG`, a
sequential startup's assembly summary records each unit's time, computes the critical path, and
says what concurrency would buy:

```
Canary assembled 8 unit(s), started in 260ms
  ...
  critical path is 150ms of the 260ms spent starting units
  start_concurrency=3 could bring that down to about 150ms (1.7x)
```

It stays quiet when startup is too short or the graph too narrow to matter.

## Letting a host drive it

Two host protocols, two entry points:

| What the host takes | Use | Who does this |
|---|---|---|
| an async context manager, `Callable[[Host], AsyncContextManager]` | `canary.lifespan` | ASGI (Starlette / FastAPI / Litestar), MCP, FastStream |
| paired startup / shutdown callbacks | `start()` and `stop()` | Quart, Sanic, arq, Dramatiq |

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
