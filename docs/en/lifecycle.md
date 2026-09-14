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

## Advancing recurses along dependencies

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

Two properties:

- **One unit runs one phase exactly once**, no matter how many units depend on it.
- **Independent dependencies advance concurrently**, so elapsed time tracks the graph's
  critical path rather than the sum of all units.

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

`stop()` drains the ledger in reverse and is the single reclamation path:

| When called | Behaviour |
|---|---|
| Never started | Ledger empty, no-op |
| Only `init()` ran | `start` ledger empty, no-op |
| After a normal start | Reclaims in reverse |
| `start()` failed midway | Reclaims whatever entered `@start`, including the one that failed |
| Called again | Ledger already drained, no-op |

One rule covers all five cases, which is why there is no state machine.

## Failure

**Startup failure.** When any `@start` raises, the ledger is unwound in reverse and the
original exception is re-raised unchanged:

```python
class Leaf(Canary):
    @start
    def go(self) -> None: ...

    @stop
    def bye(self) -> None:
        print("leaf reclaimed")


class Root(Canary):
    leaf = dep(Leaf)

    @start
    def go(self) -> None:
        raise RuntimeError("startup failed")


async with Root():        # prints "leaf reclaimed", then raises RuntimeError
    ...
```

If reclamation itself fails, that error is attached as a note on the original exception rather
than replacing it.

**Several units failing at once.** Under concurrent advancement, simultaneous failures are
combined into one `ExceptionGroup`; a lone failure is re-raised as-is, matching sequential
behaviour.

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

migrate = Phase("migrate", after=init)


class Schema(Canary):
    @migrate
    async def apply(self) -> None: ...


await unit.init()
await advance(unit, migrate)
```

`after` declares a predecessor: advancing a phase whose predecessor has not finished raises
`LifecycleError` instead of silently skipping it.

To give a new phase a reclamation pass, use `unwind()` — the pairing lives at the call site:

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
