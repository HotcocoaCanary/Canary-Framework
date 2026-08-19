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
| `ROUTE_ENTRIES_ATTR` | `@web_cocoa`'s `@on_start` | `Canary` (route entries to merge) |
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

## Serving: one merged app

`Canary` is an ASGI application. During `start()` every `@web_cocoa` unit writes its route
entries (`METHOD`, path, instance, handler) under `ROUTE_ENTRIES_ATTR`; `Canary` merges them
into **one** app, so a whole composition has a single `/openapi.json` / `/docs` / `/redoc`,
and every non-`lifespan` scope is delegated to it.

Where each unit mounts is decided by the dependency graph (`runtime/mounts.py` — a pure,
independently testable algorithm): a depth-first walk from every root chains the `prefix` of
each web unit it passes, skipping non-web units transparently. The rule is just **one
instance, many mounts** — a type is still a singleton, but a unit reached by two dependency
paths mounts at both. Each `(type, prefix)` pair is walked once, which both de-duplicates and
keeps diamond-shaped graphs from exploding.

The merge itself is the web extension's job (`build_serve_app`), and `Canary` imports it
**lazily** — never when there are no route entries, so a plain `@cocoa` composition does not
need `canary-framework[web]` installed.

## Design principles

1. **A cocoa is the smallest runnable unit.** Dependencies, state and lifecycle are all marked
   on one class.
2. **Decorators declare, they do not transform.** Units stay plain classes.
3. **Lifecycle is explicit.** `init()` / `start()` / `stop()` are called by you or by the ASGI
   lifespan — there is no hidden magic.
4. **All hooks are optional.** A dependency-only unit is complete.
5. **Markers are centralised.** One place defines the contract; no magic strings drift.
6. **Extensions load on demand.** They publish metadata through the shared markers, and
   `Canary` imports one only when it actually has to.
