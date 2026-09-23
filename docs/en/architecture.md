# Architecture

The framework is a thin layer over plain Python classes. It separates **declaration** (markers
on a class) from **interpretation** (the engine that reads them and drives).

## Layers

```
errors            exceptions, usable by any layer
   ▲
meta              declaration: phase / dep / introspect
   ▲
flow              lifecycle flow: scope / invoke / advance / unwind
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
| `core/flow/scope.py` | `Scope`, `scope_of`, no-argument construction |
| `core/flow/invoke.py` | Calling one hook |
| `core/flow/advance.py` | Advancing one phase along dependencies |
| `core/flow/unwind.py` | Reclaiming the ledger in reverse |
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

## The two rules

**Advancing** is the only recursion. What is memoised is the advance itself (a future) rather
than a done-flag, so "not started / in progress / finished" needs no separate state machine:
key absent, future pending, future done. Cycle detection rides on the same thing — a cycle is
exactly a unit that is not finished yet and sits on the current path.

Depth-first plus memoisation produces a completion order that is already a valid topological
order, so there is no separate topological sort in the framework.

**Unwinding** is the only rule that does not recurse. A dependency graph is not a tree, so
reclamation runs linearly over the ledger in reverse. What to reclaim is decided by
reachability: stopping a unit removes it from the units started directly, and every running
unit no longer reachable from those through `dep()` is reclaimed. A unit that running units
still depend on is not stopped at all.

## Concurrency

A unit's dependencies advance concurrently, scheduled by dependency — each unit waits only on
its own dependencies. When one fails, its siblings are cancelled and awaited, and the exception
group is reduced back to the single real failure.

Under concurrency the ledger order is still a valid topological order (a unit enters only after
all of its dependencies have completed), so reverse reclamation remains correct.

A single dependency is awaited directly to save a task, but every so many levels the call stack
is handed back to the event loop, so dependency-chain depth is not bounded by Python's
recursion limit.

## Invariants

1. Units are always constructed by the framework with no arguments.
2. One instance per type per scope; two separately constructed roots are two unrelated graphs.
3. Decorators only declare and never rewrite, so units stay plain classes.
4. Dependencies exist from `@init` onward.
5. Every `@init` completes before any `@start` runs.
6. `stop()` is the single reclamation path, shared by success and failure, and is idempotent.
   It undoes the `start` records it reclaims, so the graph can start again.
7. The framework knows no shells; hosting is either a context manager or the three explicit
   methods.
