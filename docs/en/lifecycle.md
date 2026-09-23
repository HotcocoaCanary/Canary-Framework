# Lifecycle

## Phases

A phase is the name of one pass. The framework ships three:

```python
from canary_framework import init, start, stop
```

They are both the decorators that mark hooks and the arguments to `advance()` and `unwind()`.

```python
class Database(Canary):
    @init
    def prepare(self) -> None: ...

    @start
    async def connect(self) -> None: ...

    @stop
    async def close(self) -> None: ...
```

One class may have several hooks in one phase; they run in definition order. One method may
belong to several phases. Hooks may be synchronous or `async def` — the framework decides
whether to await by looking at the return value, so a synchronous function returning a
coroutine works too.

## Advancing: dependencies first {#advancing}

`await unit.init()` advances `init` across the graph: dependencies first, then the unit's own
hooks.

```python
class Config(Canary): ...


class Database(Canary):
    config = dep(Config)


class Service(Canary):
    database = dep(Database)


await Service().init()      # Config -> Database -> Service
```

Three properties:

- **One unit runs one phase exactly once**, no matter how many units depend on it.
- **Independent units advance concurrently**, so elapsed time tracks the graph's critical path
  rather than the sum of all units.
- **Nothing runs until the graph checks out.** The dependency graph is built first, so a cycle,
  or a unit whose `@init` has not run before `start()`, is reported before any hook runs.

## The barrier

The return of `init()` is a barrier: every `@init` completes before any `@start` runs.

```
Config.init -> Database.init -> Service.init
          ↓ barrier
Config.start -> Database.start -> Service.start
```

This is what actually separates `@init` from `@start`. `@init` acquires nothing external, so a
failure during its pass over the graph needs no reclamation; `@start` acquires, so it has a
matching `@stop`.

Calling `start()` without `init()` raises:

```
LifecycleError: Service: @init has not run, call it before @start
```

## The ledger and reclamation

A unit is recorded in the ledger as it **enters** `@start`, not when it completes — so a unit
that fails halfway is reclaimed too.

`stop()` is the single reclamation path. It stops the unit unless something still uses it, then
tries each of its dependencies the same way:

| When called | Behaviour |
|---|---|
| Never started | Nothing to stop; its dependencies are still tried |
| Only `init()` ran | Nothing entered `@start`, no-op |
| After a normal start | Stops the unit, then the dependencies nothing else uses |
| Still in use — a dependent is starting, running or stopping | Skips the unit, no error; its dependencies are still tried |
| `start()` still running | Waits for it to finish, then decides |
| Called again | Nothing left, no-op |

A dependency shared by several units stops once the last of them has stopped. See
[Units › `stop()` is a unit action](canary.md#stop-is-a-unit-action) for examples.

Because `stop()` waits for an in-flight `start()`, do not call it from inside a `@start` hook of
the same graph: it would wait for itself. To bound shutdown, wrap the call in `asyncio.timeout`.

## Starting again

Reclamation also undoes the record of `start` for each unit it reclaims, so a stopped graph
can start again. `@init` has no reclamation phase, so its record stays and it does not run a
second time:

```python
async with service:     # init, start, stop
    ...
async with service:     # start, stop
    ...
```

A phase declared with `after=start` is undone along with `start`, and has to be advanced
again after the restart.

A failed `start()` has already released what it acquired (see below), so retrying is simply
calling it again. Units that completed the phase are not run twice:

```python
try:
    await service.start()
except ConnectionError:
    await service.start()    # the failed attempt already cleaned up after itself
```

## Failure

**Startup failure.** `start()` cleans up after itself:

- a unit whose `@start` raises runs its own `@stop` at once;
- units that depend on it do not start, and release the dependencies they were waiting on;
- units starting alongside it are not cancelled — they finish, then are released if nothing
  else uses them.

When `start()` raises, everything it brought up has been stopped, except what other running
units still use. With `X → A, B`, `A → C`, `B → C` and `B` failing:

```
C.start → A.start → B.start ✗ → B.stop → A.stop → C.stop → start() raises B's error
```

Errors raised by `@stop` during this rollback are attached as notes on the original exception.
If the caller cancels `start()`, the same rollback runs before the cancellation propagates; a
cancellation cannot carry `@stop` errors, so they go to the event loop's exception handler.

**Several units failing at once.** A failure does not cancel other units. When several fail,
the failures are combined into one `ExceptionGroup`; a lone failure is re-raised as-is, and one
failure reached through several paths is reported once.

**Reclamation failure.** One failing `@stop` does not abort the pass; the remaining units are
reclaimed and everything is raised at the end as one `ExceptionGroup`, even for a single error:

```
ExceptionGroup: 1 error(s) while stopping
  RuntimeError: could not close
    raised by Database.close
```

## Custom phases

`Phase` is public, and adding a phase requires no registration:

```python
from canary_framework import Phase, advance, init

rollback = Phase("rollback")
migrate = Phase("migrate", after=init, undo=rollback)


class Schema(Canary):
    @migrate
    async def apply(self) -> None: ...

    @rollback
    async def revert(self) -> None: ...


await unit.init()
await advance(unit, migrate)
```

`after` declares a predecessor: advancing a phase whose predecessor has not finished raises
`LifecycleError` instead of silently skipping it.

`undo` names the phase that undoes it, exactly as `stop` undoes `start`: a unit whose `@migrate`
fails runs its `@rollback` at once, and the failed advance releases what it brought up. To undo
everything that migrated:

```python
from canary_framework import scope_of, unwind

errors = await unwind(scope_of(unit), rollback, undoing=migrate)
```

## Hosting

The framework knows nothing about shells. When the host takes an async context manager:

```python
@asynccontextmanager
async def lifespan(_app):
    async with service:
        yield
```

When the host takes paired start/stop callbacks, hand it `service.init`, `service.start` and
`service.stop` directly.
