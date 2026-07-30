# What's New in 0.6.0

0.6.0 is a breaking redesign with no compatibility layer. Service, Router, and Module are now distinct explicit layers.

## Migration

| 0.5.x | 0.6.0 |
|---|---|
| `@service(config=...)` | `@service()`; put config on runtime-root Router or Module |
| `router = Router(prefix=...)` | `@router(prefix=...) class X(RouterBase)` |
| `@router.get(...)` | top-level `@get(...)` |
| `@module(services=[...])` | `@module(children=(...))` |
| Module-owned endpoint | explicit Router child |
| sync `app.init()` | `await app.init()` |
| `@before_startup/@before_shutdown` | async `on_startup/on_shutdown` |
| config class in services | config class passed to Router/Module decorator |
| any Service is ASGI | only runtime-root Router/Module is ASGI |
| pre-init empty OpenAPI | `ApplicationNotInitializedError` |

## Highlights

- Router is the smallest runnable application.
- Module composition is explicit and scoped.
- Async initialization is separate from ASGI lifespan.
- Routes, OpenAPI, and ASGI use one validated compilation pipeline.
- Root-owned OpenAPI metadata avoids nested leakage.
- Strict direction and scope rules make dependency identity predictable.

See the [Quick Start](quickstart.md) and migrated runnable examples.
