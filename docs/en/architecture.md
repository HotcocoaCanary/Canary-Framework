# Architecture

The framework is a thin layering on top of plain Python classes. It separates **declaration**
(markers on classes) from **interpretation** (the runtime that reads them).

## Layers

```
common   — shared types, exceptions and metadata markers (no framework logic)
   ▲
core     — declaration primitives: @cocoa, @on_init/@on_start/@on_stop, introspection
   ▲
runtime  — the engine: Canary, graph building, topological sort
```

The dependency direction is strictly acyclic: `runtime → core → common`. Each layer knows only
the one below it.

Inside the package every import uses the full module path — the `__init__.py` files carry only a
docstring and re-export nothing. There is exactly one public entry point: `canary_framework`.

## Markers, not magic

The framework communicates through **markers**: decorators stamp small string constants onto
classes and methods, and the runtime reads them back. Every marker is collected in
`canary_framework.common.markers`:

| Marker | Written by | Read by |
|---|---|---|
| `COCOA_ATTR` | `@cocoa` | runtime (is this a unit? what does it depend on?) |
| `ON_INIT` / `ON_START` / `ON_STOP` | the hook decorators | runtime (which hooks to run) |

A decorator only `setattr`s a marker; it never rewrites the class. That keeps units plain and
introspection cheap and side-effect free.

There is exactly one MRO scan: it walks the chain once and buckets all three hook markers, and
its result is **cached per class** because it cannot change once the class exists — while a full
lifecycle scans three times (init / start / stop). `object` is skipped: it has two dozen callable
members, none of which can ever carry our markers, and it sits at the end of every MRO.

## Two phases

1. **Declaration** — `@cocoa(deps=[...])` records dependencies and the hook decorators record
   hooks. Nothing runs.
2. **Interpretation** — `Canary` reads the markers, builds the graph, sorts it, injects, and
   drives the lifecycle. This split is what lets the pure graph algorithms be tested on their own.

## The engine

`Canary.__init__` only validates the roots. `init()` builds the graph (each type constructed once,
with no arguments), runs Kahn's topological sort, injects dependencies and runs `@on_init` in
order; `start()` runs `@on_start`; `stop()` runs `@on_stop` in reverse. The order is
deterministic and cycles surface as `CircularDependencyError`.

The graph is built with an explicit stack rather than recursion, so the depth of a dependency
chain is not bounded by Python's recursion limit. Construction calls first and only inspects the
signature after a `TypeError`, keeping `inspect.signature` on the failure path only.

Every instance on the graph is built **by the framework** — there is no second source. So "where
did this unit come from" always has one answer, and construction failures and lifecycle failures
have one way of being handled.

## It knows about no shell

`Canary` does assembly and lifecycle, nothing else. HTTP, CLIs, schedulers, message consumers —
those are **shells**, owned by other libraries, and Canary knows about none of them.

There are two ways in, because Python only has two host shapes: a host takes an async context
manager, or it takes paired startup/shutdown callbacks.

```python
app = FastAPI(lifespan=canary.lifespan)      # shape one: ASGI, MCP, FastStream
                                             # shape two: start() and stop()
```

## Invariants

1. **A cocoa is the minimum runnable unit.** Dependencies, state and lifecycle are marked on one
   class.
2. **Decorators declare, they do not transform.** Units stay plain classes and can be subclassed,
   mixed in and nested.
3. **Every instance is constructed by the framework with no arguments.** Anything needing outside
   input happens in a lifecycle hook, because only what happens there has a matching reclamation
   step.
4. **Assembly is synchronous and side-effect free.** Building, sorting and injecting run no hooks
   and need no event loop.
5. **Anything assembly can detect, assembly raises** — name clashes, cycles, units needing
   constructor arguments, dependencies that are not cocoas.
6. **The runtime knows about no shell.** There are two ways in: `lifespan` and the explicit
   methods.
