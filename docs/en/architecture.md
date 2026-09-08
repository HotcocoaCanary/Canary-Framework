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
   ▲
web      — optional extension: @web_cocoa, route decorators, dispatch, OpenAPI
```

The dependency direction is strictly acyclic: `web → runtime → core → common`. Each layer knows
only the one below it.

Inside the package every import uses the full module path — the `__init__.py` files carry only a
docstring and re-export nothing. There are exactly two public entry points:
`canary_framework` and `canary_framework.web`.

## Markers, not magic

The framework communicates through **markers**: decorators stamp small string constants onto
classes and methods, and the runtime reads them back. Every marker is collected in
`canary_framework.common.markers`:

| Marker | Written by | Read by |
|---|---|---|
| `COCOA_ATTR` | `@cocoa` | runtime (is this a unit? what does it depend on?) |
| `ON_INIT` / `ON_START` / `ON_STOP` | the hook decorators | runtime (which hooks to run) |
| `ROUTE_ATTR` | `@get` / `@post` / … | web extension (method, path, status code, doc metadata) |
| `WEB_ATTR` | `@web_cocoa` | runtime (which units carry routes) and the web extension (prefix, title, tags) |

A decorator only `setattr`s a marker; it never rewrites the class. That keeps units plain and
introspection cheap and side-effect free.

There is exactly one MRO scan (`core.decorator.introspect.marked_members`): lifecycle hooks and
HTTP routes are the same question — methods on a class carrying a marker — and differ only in the
payload. Its result is cached per class, because it cannot change after the class is created.

## Two phases

1. **Declaration** — `@cocoa(deps=[...])` records dependencies, the hook decorators record hooks,
   `@get` records routes. Nothing runs.
2. **Interpretation** — `Canary` reads the markers, builds the graph, sorts it, injects, and
   drives the lifecycle. This split is what lets the pure graph algorithms be tested on their own.

## The engine

`Canary.__init__` only validates the roots. `init()` builds the graph (each type constructed once,
with no arguments), runs Kahn's topological sort, injects dependencies and runs `@on_init` in
order; `start()` runs `@on_start` and merges the serving app; `stop()` runs `@on_stop` in reverse.
The order is deterministic and cycles surface as `CircularDependencyError`.

Every instance on the graph is built **by the framework** — there is no second source. So "where
did this unit come from" always has one answer, and construction failures and lifecycle failures
have one way of being handled.

## Serving: merged into one app

`Canary` is an ASGI app. At the end of `start()` it picks the units carrying `WEB_ATTR` and hands
them to the web extension, which collects and merges them into **one** Starlette app — so the
whole composition exposes a single `/openapi.json` and `/docs`, and every non-`lifespan` scope is
delegated to it.

**The runtime does no path arithmetic**: what a URL looks like is the web extension's business,
and the runtime only knows which units exist. `prefix` is each unit's absolute prefix and is
joined into the full path inside the extension's `collect_routes`.

The merge itself is done by the web extension (`build_serve_app`), which `Canary` imports
**lazily** — it never happens when the graph has no web unit, so a pure `@cocoa` composition does
not need `canary-framework[web]` installed.

## The request path: compiled at assembly, no reflection per request

At assembly time the web extension compiles every handler's signature into a `HandlerPlan`: where
each parameter comes from, which validator to use, whether it has a default, how to serialise the
return value. When a request arrives the framework walks a tuple, pulls values from their sources
and runs validators that already exist — no `get_type_hints`, no `inspect.signature`, no
`TypeAdapter` construction.

The same plan feeds OpenAPI generation. **Dispatch and the document read the same object**, so an
inconsistency like "the document says query, the code reads the body" is structurally impossible.

## Design principles

1. **A cocoa is the minimum runnable unit.** Dependencies, state and lifecycle are marked on one
   class.
2. **Decorators declare, they do not transform.** Units stay plain classes.
3. **The framework only builds empty shells.** Anything needing outside input happens in the
   lifecycle — because only what happens there has a matching reclamation step.
4. **The lifecycle is explicit.** `init()` / `start()` / `stop()` are called by you or by the ASGI
   lifespan.
5. **Silent failure must be made loud.** "Written, no error, no effect" is the hardest kind of
   problem to find, so assembly would rather refuse.
6. **A capability belongs in the framework only when users cannot build it themselves.** Something
   you can write in ten lines does not deserve a public entry point.
7. **Markers are collected in one place; extensions load on demand.** The contract is defined once,
   and `Canary` imports an extension only when it really needs it.
