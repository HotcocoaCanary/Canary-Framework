# Architecture

The framework forms a thin layer over Python's native object and async context-manager protocols.

## The layering

```
普通 Python Class
      │  @canary
      ▼
Canary
      │
      ├── __init__  → construction / dependency injection
      ├── @start    → startup hook  → __aenter__
      └── @stop     → stop hook     → __aexit__
      ▲
Flock (optional orchestrator)
```

A Canary is a plain class plus a declaration. `@canary` records metadata — dependency parameter names and lifecycle hook names — and rebuilds the class as a `Canary` subclass so it inherits the context-manager protocol and state machine.

## Two usage modes

The framework has one engine and two ways to drive it:

- **Under a `Flock`** — for full applications. `Canary.run()` returns a `Flock` that resolves the dependency graph, sorts it, and runs construction and startup in order.
- **Standalone** — when you already own the instance. A Canary is directly an async context manager:

```python
async with database:
    ...
```

## Dependency discovery

`@canary` classifies `__init__` parameters by name at decoration time (string annotations need not resolve yet). At graph-build time, `Flock` resolves each dependency to a concrete, registered Canary type. This split enables forward references and reliable cycle detection.

## Ordering

The dependency graph determines every order:

- **Construction** — topological order.
- **Startup** — topological order.
- **Shutdown** — reverse topological order.
- **Rollback** — reverse topological order.

Topological sorting uses Kahn's algorithm with ties broken by `__qualname__` for a deterministic result.

## Design principles

1. **Canary is the smallest runnable unit.** Dependencies, state, and lifecycle all live on one class.
2. **`__init__` is the DI entry point.** No dependency DSL.
3. **Lifecycle builds on Python's native protocol.** Start → `__aenter__`, stop → `__aexit__`.
4. **`@start` / `@stop` are declarative.** The framework wires them into the protocol; it never injects magic methods.
5. **All hooks are optional.** A dependency-only Canary is complete.
6. **Decorators don't change method types.** Static type checkers keep working.
7. **Dependencies determine lifecycle order.**
8. **`Flock` only orchestrates.** It is never a precondition for running a Canary.
