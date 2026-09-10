# API Reference

Everything below is exported from `canary_framework` unless stated otherwise.

## `cocoa`

```python
def cocoa(cls=None, *, deps: list[type] | None = None)
```

Marks `cls` as a cocoa — the minimum unit. `deps` is an ordered list of dependency types. Usable
directly or as a decorator factory:

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...
```

Units are always constructed by the framework **with no arguments**: `__init__` may not have
required parameters, or `Canary(...)` raises `ConstructionError`.

## `on_init` / `on_start` / `on_stop`

```python
def on_init(fn) -> fn
def on_start(fn) -> fn
def on_stop(fn) -> fn
```

Register a method as a lifecycle hook. Each accepts sync or async functions; a phase may have any
number of hooks, and mixin hooks run before the class's own.

## `Canary`

```python
class Canary(*roots: type, start_concurrency: int | None = None)
```

The orchestrator. Construction is assembly: build the graph (each type constructed once, with no
arguments), sort it, inject dependencies — all synchronously. Assembly errors
(`ConstructionError` / `InjectionError` / `CircularDependencyError`, `TypeError` for a
non-cocoa) are raised on this line.

`start_concurrency`: `None` (default) is strictly sequential; a positive integer lets independent
units start together, at most that many at once. See
[Lifecycle · Concurrent startup](lifecycle.md#concurrent-startup).

### Properties

| Property | Type | Meaning |
|---|---|---|
| `state` | `LifecycleState` | current lifecycle state |
| `order` | `tuple[type, ...]` | topological start order (dependencies first) |
| `instances` | `tuple[object, ...]` | the instances in that order |
| `roots` | `tuple[type, ...]` | the roots given at construction |

### `__getitem__`

```python
def __getitem__(self, cls: type[T]) -> T
```

Returns the shared singleton for `cls`, or raises `KeyError`.

### `init`

```python
async def init(self) -> None
```

`READY → INITIALIZED`. Runs every `@on_init` — settling in. Dependencies were injected at
construction; here each unit does the preparation that needs only its dependencies and no
external resource. On failure the state becomes `FAILED` and the exception propagates; the ledger
is empty, so nothing is reclaimed.

It is a barrier: only once every `@on_init` has completed may any `@on_start` run. The barrier
is this method's return.

### `start`

```python
async def start(self) -> None
```

`INITIALIZED → STARTED`. Runs every `@on_start` — going to work. A unit is ledgered the moment
it enters `@on_start`. Calling it from `READY` (having skipped `init()`) raises
`LifecycleError: call init() before start()`.

If any step fails, every unit that **entered** `@on_start` (including the one that failed) is
reclaimed in reverse, and the original exception is re-raised with any unwind failures attached
as notes.

### `stop`

```python
async def stop(self) -> None
```

Runs `@on_stop` in reverse topological order. **The single reclamation path**: callable from
`STARTED` and from `FAILED`, idempotent, a no-op when nothing ever started. A failing `@on_stop`
does not abort the rest — the errors are collected and raised together as an `ExceptionGroup`.

### `lifespan`

```python
@asynccontextmanager
def lifespan(self, _host: object = None) -> AsyncContextManager[None]
```

The host-facing entry point: `start()` on enter, `stop()` on exit, **yielding
`None`**.

`_host` accepts the host a framework passes in (ASGI's `lifespan(app)`, MCP's
`lifespan(server)`) and defaults to `None`, so it also works standalone as
`async with canary.lifespan():`.

```python
app = FastAPI(lifespan=canary.lifespan)
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
server = MCPServer("demo", lifespan=canary.lifespan)
```

Yielding `None` is required: the ASGI lifespan protocol treats the yielded value as a mapping to
merge into `scope["state"]`.

### `__aenter__` / `__aexit__`

The async context manager protocol, wrapping `start()` / `stop()`, **handing back the
container** — it serves your own code:

```python
async with Canary(Root) as canary:
    canary[SomeUnit].do_something()
```

## Enums

### `LifecycleState`

`READY`, `INITIALIZING`, `INITIALIZED`, `STARTING`, `STARTED`, `STOPPING`, `STOPPED`, `FAILED`.
Each action has an in-progress and a settled state; it starts at `READY` because assembly is
already done inside `Canary(...)`.

### `State`

(`canary_framework.common.type`) The base of every state enum; a mounting point for `issubclass`
checks.

## Exceptions

| Exception | Base | Meaning |
|---|---|---|
| `CanaryError` | `Exception` | the root of every framework and extension error |
| `CircularDependencyError` | `CanaryError` | a cycle in the graph; `.cycle` lists the type names |
| `ConstructionError` | `CanaryError` | the unit needs constructor arguments and cannot be built |
| `InjectionError` | `CanaryError` | two dependencies claim the same attribute; `.attribute` / `.claimants` |
| `LifecycleError` | `CanaryError` | an illegal lifecycle transition |

Everything inherits `CanaryError`, so a single `except CanaryError` catches them all. Future
extensions should inherit it too.

## Environment variables

| Variable | Effect |
|---|---|
| `CANARY_LOG_LEVEL` | the level of the `canary` logger tree; `DEBUG` also prints the assembly summary |
| `CANARY_SLOW_CALLBACK_SECONDS` | threshold in seconds for the event-loop lag probe; a development tool, off by default |

## Introspection (`canary_framework.core.decorator.introspect`)

| Function | Purpose |
|---|---|
| `is_cocoa(cls)` | whether `cls` is marked with `@cocoa` |
| `deps_of(cls)` | the declared dependencies (a tuple) |
| `init_hooks(instance)` / `start_hooks(instance)` / `stop_hooks(instance)` | the hooks of one phase, base-first |
| `to_snake(name)` | (`core.infra.naming`) `UserService` → `user_service` |

## Graph algorithms (`canary_framework.runtime.graph`)

| Function | Purpose |
|---|---|
| `build_graph(roots)` | instantiate every root and its transitive dependencies, once each, with no arguments |
| `topological_sort(graph)` | Kahn's algorithm; raises `CircularDependencyError` on a cycle |
