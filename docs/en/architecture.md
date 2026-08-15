# Architecture

The framework is a thin, layered layer over plain Python classes. It separates **declaration**
(markers on classes) from **interpretation** (the runtime that reads them).

## The layers

```
common   — shared types, errors and metadata markers (no framework logic)
   ▲
core     — declaration primitives: @cocoa, @on_init/@on_start/@on_stop, introspection
   ▲
runtime  — the engine: Canary, graph building, topological sort
   ▲
web      — optional extension: @web_cocoa, route decorators, OpenAPI
```

Dependency direction is strict and acyclic: `web → runtime → core → common`. Each layer knows
only the layer beneath it.

## Markers, not magic

The framework communicates through **markers** — small string constants stamped onto classes
and methods by decorators, and read back by the runtime. All markers are centralised in
`canary_framework.common.markers`, grouped by subsystem:

| Marker | Written by | Read by |
|---|---|---|
| `COCOA_ATTR` | `@cocoa` | runtime (is it a unit? what are its deps?) |
| `ON_INIT` / `ON_START` / `ON_STOP` | the hook decorators | runtime (which hooks to run) |
| `SERVE_ATTR` | a unit's `@on_start` | `Canary` (the serving app to delegate to) |
| `ROUTE_ATTR` / `WEB_ATTR` | `@get`/… and `@web_cocoa` | the web extension |

Decorators only `setattr` a marker; they never rewrite the class. This keeps units as plain
classes and makes introspection cheap and side-effect-free.

## Two phases

1. **Declaration** — `@cocoa(deps=[...])` records dependencies; `@on_init`/`@on_start`/`@on_stop`
   record hooks. Nothing runs yet.
2. **Interpretation** — `Canary` reads the markers, builds the graph, orders it, and drives the
   lifecycle. This split lets the pure graph algorithms be tested in isolation.

## The engine

`Canary.__init__` validates roots and builds a graph of instances. `init()` runs Kahn's
topological sort over `deps=[...]` and executes `@on_init` in order; `start()` injects
dependencies then runs `@on_start`; `stop()` runs `@on_stop` in reverse order. The sorting is
deterministic, and a cycle surfaces as `CircularDependencyError`.

## Serving: duck typing, not coupling

`Canary` is an ASGI application without knowing any concrete extension. During `start()`, it
sweeps its instances for the `SERVE_ATTR` marker; if a unit exposed a serving app (a Starlette
app, in the web extension's case), `Canary` keeps it and delegates every non-`lifespan` scope
to it.

This is the whole extension story: an extension needs only to (1) use the shared markers and
(2) expose an app under `SERVE_ATTR` during `start()`. `Canary` itself never imports it.

## Design principles

1. **A cocoa is the smallest runnable unit.** Dependencies, state and lifecycle are all marked
   on one class.
2. **Decorators declare, they do not transform.** Units stay plain classes.
3. **Lifecycle is explicit.** `init()` / `start()` / `stop()` are called by you or by the ASGI
   lifespan — there is no hidden magic.
4. **All hooks are optional.** A dependency-only unit is complete.
5. **Markers are centralised.** One place defines the contract; no magic strings drift.
6. **The runtime is duck-typed over extensions.** `Canary` delegates to a serving app by
   marker, never by importing it.
