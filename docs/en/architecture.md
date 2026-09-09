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

The graph is built with an explicit stack rather than recursion — how deep a dependency chain
goes is the user's data and should not be bounded by Python's recursion limit. Construction calls
first and only inspects the signature after a `TypeError`: taking a signature exists to explain a
failure, and should not be charged to every unit that constructs fine (it used to be 90% of graph
building).

Every instance on the graph is built **by the framework** — there is no second source. So "where
did this unit come from" always has one answer, and construction failures and lifecycle failures
have one way of being handled.

## It knows about no shell

`Canary` does assembly and lifecycle, nothing else. HTTP, CLIs, schedulers, message consumers —
those are **shells**, owned by other libraries, and Canary knows about none of them. There is one
way in: let the host wrap its own runtime in the async context manager.

```python
@asynccontextmanager
async def lifespan(_app):
    async with canary:
        yield
```

That boundary is deliberate. A web layer used to live in this repository (`@web_cocoa`, route
decorators, parameter binding, OpenAPI — about 1300 lines), but it did the same job as FastAPI
and Starlette, and that is not where this framework differs — the difference is in dependency
assembly and lifecycle. Rebuilding it only forces a permanent chase after WebSocket, file
uploads and middleware, and that half is where nearly every bug came from.

## Design principles

1. **A cocoa is the minimum runnable unit.** Dependencies, state and lifecycle are marked on one
   class.
2. **Decorators declare, they do not transform.** Units stay plain classes.
3. **The framework only builds empty shells.** Anything needing outside input happens in the
   lifecycle — because only what happens there has a matching reclamation step.
4. **The lifecycle is explicit.** `init()` / `start()` / `stop()` are called by you or by the
   host's lifespan.
5. **Silent failure must be made loud.** "Written, no error, no effect" is the hardest kind of
   problem to find, so assembly would rather refuse.
6. **A capability belongs in the framework only when users cannot build it themselves.** Something
   you can write in ten lines does not deserve a public entry point.
7. **Do not rebuild what others already did well.** Stand on the existing Python ecosystem
   instead of competing with it.
