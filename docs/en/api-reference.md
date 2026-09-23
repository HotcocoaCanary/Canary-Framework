# API Reference

Every public name is exported from `canary_framework`.

```python
from canary_framework import (
    Canary, dep,                                  # declaration
    init, start, stop, Phase,                     # phases
    enter, leave, Scope, scope_of, deps_of,       # engine
    CanaryError, DeclarationError, ConstructionError,
    CircularDependencyError, LifecycleError,      # exceptions
)
```

## Declaration

### `class Canary`

The unit base class. Subclass it and you have a unit.

| Member | Description |
|---|---|
| `async init()` | Advance the `init` phase along dependencies. |
| `async start()` | Advance the `start` phase. On failure, releases what it brought up before raising. Raises `LifecycleError` if `init()` has not run. |
| `async stop()` | Stop this unit unless a dependent is starting, running or stopping, then try its dependencies the same way. On the root, the whole graph. Idempotent. |
| `async __aenter__()` | Calls `init()` then `start()`, reclaiming and re-raising on failure. Returns self. |
| `async __aexit__(...)` | Calls `stop()`; never suppresses the exception. |

Subclasses may override these and compose with `super()`. Phase hooks must not use these names.

### `dep(cls)`

Declare a dependency; typed to return an instance of `cls`.

```python
class UserService(Canary):
    database = dep(Database)
```

- You choose the attribute name; it is unrelated to the dependency's class name.
- Dependencies exist from `@init` onward; reading one in `__init__` raises `LifecycleError`.
- Raises `DeclarationError` when `cls` is not a `Canary` subclass, while the class body is
  being evaluated.

## Phases

### `init` / `start` / `stop`

The three `Phase` instances the framework ships, which are also the decorators that mark hooks.

```python
class Database(Canary):
    @start
    async def connect(self) -> None: ...
```

`start`'s predecessor is `init`, and leaving it runs `stop`:
`start = Phase("start", after=init, leave=stop)`.

### `class Phase(name, *, after=None, leave=None)`

A phase. Calling it marks a method as one of its hooks.

| Parameter | Description |
|---|---|
| `name` | The phase name; the scope keys each unit's state in the phase by it. |
| `after` | The predecessor phase. Entering before it has been entered raises `LifecycleError`. |
| `leave` | The phase whose hooks run when this one is left: by `leave()`, and at once for a unit that fails or is cancelled while entering. `start`'s is `stop`. |

```python
rollback = Phase("rollback")
migrate = Phase("migrate", after=init, leave=rollback)
```

## Engine

`Canary`'s methods are these two functions: `unit.init()` is `enter(unit, init)`,
`unit.start()` is `enter(unit, start)`, and `unit.stop()` is `leave(unit, start)`. Call them
directly for phases of your own.

### `async enter(unit, phase)`

Enter `phase` across `unit`'s dependency graph: dependencies first, then the unit's own hooks.
One unit runs one phase exactly once; independent units enter concurrently. The graph is
checked first — a cycle, or a unit that has not entered the predecessor phase, is reported
before any hook runs. A failure does not cancel other units; when `phase` has a `leave`, a unit
that fails runs its leave hooks at once, and the call releases what it brought up before
raising.

### `async leave(unit, phase)`

Leave `phase` on `unit`: the unit first — skipped, without an error, while a dependent is
entering, entered or leaving — then each of its dependencies the same way. Runs the hooks of
`phase.leave`. On the root, the whole graph. Waits for the unit to finish entering if it is
still entering. One failing hook does not stop the rest; the errors are raised together as an
`ExceptionGroup`. Raises `LifecycleError` when `phase` declares no `leave`.

```python
await enter(unit, migrate)
await leave(unit, migrate)      # runs @rollback
```

### `class Scope`

The state one run shares.

| Attribute | Description |
|---|---|
| `instances` | `dict[type, object]`, type to shared instance. |
| `graph` | `dict[type, tuple[type, ...]]`, the dependency graph: each unit's dependencies, in topological order. |
| `dependents` | `dict[type, list[type]]`, the graph's reverse edges. |
| `tracks` | `dict[tuple[type, str], Track]`, each unit's state in each phase. |
| `known` | `dict[str, Phase]`, the phases entered in this scope. |

`graph`, `dependents`, `tracks` and `known` are for inspection; their shape is not covered by the
[compatibility promise](versioning.md#public-api).

| Method | Description |
|---|---|
| `instance(cls)` | The single instance of that type in this scope, constructed on first use. |
| `adopt(unit)` | Register an instance into this scope. |
| `provide(cls, unit)` | Make `unit` the instance of `cls` for the whole graph. Call before the lifecycle begins. |
| `resolve(cls)` | The type standing in for `cls`: a provided unit's type, or `cls`. |
| `key_of(unit)` | The type `unit` is registered under: for a provided unit, the type it replaces. |
| `entered(phase)` | The units holding what `phase` acquired — entered and not yet left — by type. |

### `scope_of(unit)`

The scope a unit belongs to. A root unit gets a fresh one on first use.

### `deps_of(cls)`

The dependencies `cls` declares: base class first, in definition order, deduplicated by type.

## Exceptions

All inherit `CanaryError`, so one `except CanaryError` catches everything.

| Exception | Raised when |
|---|---|
| `CanaryError` | Base class; never raised directly. |
| `DeclarationError` | `dep()` was given something that is not a `Canary` subclass. |
| `ConstructionError` | A unit requires constructor arguments. Carries `unit`. |
| `CircularDependencyError` | The dependency graph has a cycle; raised before any hook runs. Carries `cycle`, the path that reaches it. |
| `LifecycleError` | A unit used outside its lifecycle: a dependency read in `__init__`, or a phase entered before its predecessor. |

Several reclamation failures are combined into the standard library's `ExceptionGroup`, which
is not a `CanaryError`.
