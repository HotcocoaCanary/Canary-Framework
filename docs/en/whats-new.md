# What's New in 0.5.x

This page summarizes the router redesign and request-handling fixes that shipped in the
`0.5.2` line, and what — if anything — you need to change in your code.

!!! tip "Where to look next"
    This page is a summary. For the full internals, see [Architecture & Internals](core.md); for
    day-to-day routing usage, see [Web & Routing](web.md); for the config fields mentioned below,
    see [Configuration](configuration.md).

## Router redesign: single-point memoized assembly

Before `0.5.2`, route aggregation, OpenAPI generation, and doc-endpoint registration were spread
across several code paths, with separate behavior depending on whether a service ran standalone or
was mounted inside a module. That branching is gone.

=== "Mental model — before"

    ```
    standalone service  ──►  one assembly path  ──►  routes + docs
    service in a module ──►  a DIFFERENT assembly path  ──►  routes + docs
                             (mount-at-/{ServiceName}, first-router-wins docs,
                              docs (re)built on startup())
    ```

=== "Mental model — after"

    ```
    ANY node you run (a lone @service OR a @module)
            │
            ▼
    _cf_collect_routes()  →  list[ResolvedRoute]   (whole subtree, prefixes already composed)
            │
            ▼
    _cf_assemble()  →  Assembled(router, openapi)   (memoized — runs at most once)
            │
            ├─► one Starlette routing table
            └─► one OpenAPI document + /docs, /redoc, /openapi.json
    ```

The key idea: **standalone == mounted**. A lone service run directly and that same service
composed inside a module serve identical paths — the only difference is the scope of the subtree
that gets collected. There's one assembly method, memoized on first access, so it runs at most once
per node regardless of how many times you touch `asgi_app` or call `openapi()`.

Two things fall out of this:

- **`ServiceBase.openapi()`** is a new public method — call it any time (even outside a running
  server) to get the memoized OpenAPI dict for whatever subtree you're running.
- **Route collisions are now a real error.** If two routes resolve to the same `(method,
  full_path)` anywhere in the composed tree, assembly raises `ValueError` instead of silently
  picking one.

!!! info "Deleted mechanics — don't look for these anymore"
    `_collect_routes`, `_route_handler`, `_cf_get_root_routes`, `_cf_collect_route_infos`,
    `_cf_generate_openapi`, `get_mount_path`, "first-router-wins" doc registration, and
    mount-at-`/{ServiceName}` are all gone. If you see them referenced in older docs or forks,
    treat that as stale.

## Fixed request-handling bugs

Five bugs in request handling were fixed as part of this cycle:

- **OpenAPI schema cache leak** — the schema registry is now a per-generation local instead of a
  process-wide global, so regenerating OpenAPI docs in the same process no longer produces dangling
  `$ref`s.
- **Path parameter + request body together** — request handling now binds every kwarg by
  **parameter name** end-to-end; `PUT /x/{id}` with a body no longer 500s.
- **Missing required query parameter** — now correctly returns **422** (previously 500).
- **Boolean query parameters** — `1/true/yes/on` (case-insensitive) → `True`, `0/false/no/off` →
  `False`, anything else → 422 (previously only the literal `true` was recognized).
- **Tuple returns** — `(body, status_code)` now correctly sets the HTTP status code (previously the
  tuple was stringified and always returned as `200`).

## Migration

!!! warning "Migration: explicit prefixes only (D4)"
    **Behavior change.** There is no more `/{ServiceName}` auto-namespacing. A service whose
    `Router` has no `prefix` now serves its routes at the bare path, not at
    `/{ServiceName}/...`.

    **If you had a service relying on implicit mounting:**

    ```python
    # Before (implicit /{ServiceName} namespace — no longer happens)
    @service()
    class Users(ServiceBase):
        router = Router()  # used to be reachable at /Users/...

        @router.get("/{user_id}")
        async def get_user(self, user_id: int): ...
    ```

    ```python
    # After — give it an explicit prefix to reproduce the old path
    @service()
    class Users(ServiceBase):
        router = Router(prefix="/users")

        @router.get("/{user_id}")
        async def get_user(self, user_id: int): ...
    ```

    **Checklist:**

    1. Search your services for `Router()` (no `prefix=`) or `Router(tags=...)` without a prefix.
    2. Add an explicit `prefix=` to each one that needs a namespace.
    3. Run your app once — a `(method, full_path)` collision anywhere in the composed tree raises
       `ValueError` at assembly time, so conflicts surface immediately rather than silently
       shadowing a route.

    See [Mounting Routers](web.md#mounting-routers) for the full explanation and more examples.

## Versioning policy

Canary Framework stays on the **`0.5.x`** line as long as the core design philosophy is unchanged:

- service is the smallest unit;
- a module composes services and *is* a service;
- dependency injection via type annotations;
- a decorator-driven API.

Under that policy, new features and fixes — including everything on this page — ship as `0.5.x`
releases. Internal refactors or behavior tightening (like the fixes above) do **not** advance the
version line on their own; the line only advances when the fundamental design changes. In other
words: **if you're building on the current model, `0.5.x` is where you want to stay**, and it will
keep receiving fixes and improvements.

See the [CHANGELOG](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md) for
the full version history and the versioning policy in its original wording.
