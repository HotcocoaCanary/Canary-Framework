# Architecture

The framework is a thin layer over plain Python classes. It separates **declaration** (markers
on a class) from **interpretation** (the engine that reads them and drives).

## Layers

```
errors            exceptions, usable by any layer
   ▲
meta              declaration: phase / dep / introspect
   ▲
flow              lifecycle flow: scope / graph / invoke / enter / leave
   ▲
canary            facade: the Canary base class and dep()
```

The dependency direction is strictly one-way: `canary → flow → meta → errors`. Only
`canary` depends on both sides, which is exactly a facade's job.

This is not merely documented — `tests/test_layering.py` parses every module's imports with
`ast` and asserts the direction, so any reverse dependency fails the test.

## Modules

| Module | Contents |
|---|---|
| `core/errors.py` | Five exceptions, all inheriting `CanaryError` |
| `core/meta/phase.py` | `Phase` plus `init` / `start` / `stop` |
| `core/meta/dep.py` | The `Dep` descriptor |
| `core/meta/introspect.py` | One MRO walk reading dependencies and hooks, cached per class |
| `core/flow/scope.py` | `Scope`, each unit's state in each phase, no-argument construction |
| `core/flow/graph.py` | Building the dependency graph and detecting cycles |
| `core/flow/invoke.py` | Calling one hook |
| `core/flow/enter.py` | `enter()`: entering a phase over the graph, dependencies first |
| `core/flow/leave.py` | `leave()`: leaving a phase over the graph, the unit first |
| `core/canary.py` | The `Canary` base class and `dep()` |

## Markers, not rewriting

Decorators write one marker on a method and never rewrite the class. Units keep every property
of a plain class: subclassing, mixins, nesting.

| Marker | Written by | Read by |
|---|---|---|
| `__canary_phases__` | Phase decorators | `introspect` (which methods belong to which phase) |
| `_canary_scope` | `Scope.adopt` | `Dep.__get__` (where to resolve a dependency) |

Dependencies are not expressed with a marker at all: a `Dep` is a class attribute, so it holds
the class object itself rather than a name.

## Hook resolution

One MRO walk collects dependencies and marked attribute names together, and the result is
cached per class — declarations do not change after class creation.

Hooks resolve by **attribute name**, so the semantics match ordinary methods:

- A subclass overriding a hook of the same name replaces it; use `super()` to compose.
- A subclass overriding it without re-marking it removes the hook.
- Mixin hooks under different names all apply, base class first.

## The dependency graph

The first time a unit is entered, it joins the scope's dependency graph together with
everything it depends on. Nodes are the types units are registered under; edges come from
`dep()` declarations, resolved through `Scope.provide()` substitutions. The graph is static —
`dep()` is a class-level declaration and substitutions are refused once the lifecycle has begun
— so it is built once and never changes.

Building it is an iterative depth-first walk. A **cycle** is found there, before any hook runs,
and reported with the path that reaches it. A node joins only after its dependencies have, so
the graph's insertion order is itself a topological order.

## Unit state

Each unit has one state per phase:

| State | Meaning |
|---|---|
| idle | Not entered, or left |
| entering | Claimed by an `enter()`: waiting for its dependencies, or running its hooks |
| entered | Every hook succeeded |
| failed | Failed or cancelled while entering, and not left yet |
| leaving | Running its leave hooks — it still uses its dependencies meanwhile |

A unit is **in use** while a dependent is entering, entered, failed or leaving. That one
definition decides both when a unit may be left and whether a dependency may start. Waiting
still uses futures — a dependent waits on the outcome of its dependency's entering, and a
second `leave()` of the same unit waits on the first — but what a unit *is* is always read from
its state, never pieced together.

## The two rules

**Entering** runs dependencies first. `enter()` claims the idle units the call reaches and gives
each a task that waits for its dependencies and then runs its hooks, so independent units enter
concurrently and nothing recurses. A unit another call is already entering is waited on, not
run again.

**Leaving** runs the unit first. `leave()` skips a unit that is in use and otherwise runs its
leave hooks; either way it then tries each dependency the same way, concurrently, each in a
task of its own. A unit that was skipped or idle is passed through once per call; a unit that
actually left always carries on to its dependencies, since one of them may have just lost its
last user. The work of one call is therefore proportional to the size of the graph.

The two rules mirror each other on the same graph, and that symmetry is what makes `stop()` a
unit action like `init()` and `start()`. A phase names the phase that runs when it is left with
`leave`; `start`'s is `stop`.

## Concurrency and failure

A failure does not cancel other units: every unit finishes on its own. A unit whose dependencies
did not all enter runs no hooks and fails with the same exception. When the phase has a `leave`,
a unit that fails or is cancelled leaves at once — without the in-use check, since the
dependents waiting on it never used it — and then tries its dependencies. So a failed `enter()`
returns only after everything it brought up has been released, except what other running units
still use. Without a `leave`, failed units return to idle when the call returns, so it can be
retried.

The failures are then reduced to the real ones — a failure reached through several paths is
reported once. Waiting on another unit never cancels it. When the caller cancels `enter()`, the
same rollback completes before the cancellation propagates; leave errors that a cancellation
cannot carry go to the event loop's exception handler.

## Invariants

1. Units are always constructed by the framework with no arguments.
2. One instance per type per scope; two separately constructed roots are two unrelated graphs.
3. Decorators only declare and never rewrite, so units stay plain classes.
4. Dependencies exist from `@init` onward.
5. Every `@init` completes before any `@start` runs.
6. `stop()` is the single reclamation path, shared by success and failure, and is idempotent.
   It undoes the `start` records it reclaims, so the graph can start again.
7. A unit is never stopped while a unit that depends on it is starting, running or stopping.
8. A failed `start()` returns only after releasing what it brought up.
9. Cycles are reported before any hook runs.
10. The framework knows no shells; hosting is either a context manager or the three explicit
   methods.
