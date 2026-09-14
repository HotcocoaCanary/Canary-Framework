# API Reference

Every public name is exported from `canary_framework`.

```python
from canary_framework import (
    Canary, dep,                                  # declaration
    init, start, stop, Phase,                     # phases
    advance, unwind, Scope, scope_of, deps_of,    # engine
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
| `async start()` | Advance the `start` phase. Raises `LifecycleError` if `init()` has not run. |
| `async stop()` | Reclaim the whole scope's ledger in reverse. Idempotent. |
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

`start`'s predecessor is `init`. `stop` is not advanced by `advance()`; `Canary.stop()`
consumes the ledger with it.

### `class Phase(name, *, after=None)`

A phase. Calling it marks a method as one of its hooks.

| Parameter | Description |
|---|---|
| `name` | The phase name; the scope keys its advance records and ledgers by it. |
| `after` | The predecessor phase. Advancing before it has finished raises `LifecycleError`. |

```python
migrate = Phase("migrate", after=init)
```

## Engine

### `async advance(unit, phase)`

Advance `phase` across `unit`'s dependency graph: dependencies first, then the unit's own
hooks. One unit runs one phase exactly once; independent dependencies advance concurrently.

### `async unwind(scope, phase, *, undoing)`

Drain `undoing`'s ledger in reverse, running `phase`'s hooks on each unit. One failing hook
does not abort the pass; errors are collected and returned as a list. The ledger is drained
either way.

```python
errors = await unwind(scope_of(unit), stop, undoing=start)
```

### `class Scope`

The state one run shares.

| Attribute | Description |
|---|---|
| `instances` | `dict[type, object]`, type to shared instance. |
| `phases` | `dict[tuple[type, str], Future]`, each advance itself. |
| `entered` | `dict[str, list[object]]`, phase name to the units that entered, in order. |

| Method | Description |
|---|---|
| `instance(cls)` | The single instance of that type in this scope, constructed on first use. |
| `adopt(unit)` | Register an instance into this scope. |

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
| `CircularDependencyError` | The dependency graph has a cycle. Carries `cycle`, the path walked. |
| `LifecycleError` | A unit used outside its lifecycle: a dependency read in `__init__`, or a phase advanced before its predecessor. |

Several reclamation failures are combined into the standard library's `ExceptionGroup`, which
is not a `CanaryError`.
