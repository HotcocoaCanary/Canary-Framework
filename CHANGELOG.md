# Changelog / 变更日志

This project follows Keep a Changelog and Semantic Versioning.

## [0.6.0] — 2026-07-30

### Breaking architecture / 破坏性架构变更

0.6.0 makes Service, Router, and Module separate explicit layers. There is no compatibility layer for 0.5.x APIs.

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

### Added

- Standalone `RouterBase` applications and scoped `ModuleBase` composition.
- Immutable route specifications, context propagation, route validation, and one Assembly compiler.
- Strict dependency direction, parent reuse, sibling isolation, and explicit promotion.
- Root-owned OpenAPI compilation with local schema registries and conflict detection.
- Explicit async lifecycle states: `CREATED`, `INITIALIZED`, `STARTED`, `STOPPED`, `FAILED`.

### Changed

- `await app.init()` is mandatory; lifespan only starts and stops an initialized root.
- Services are lifecycle/DI/domain objects and are never served directly.
- Modules cannot own business endpoints; they aggregate Router descendants.
- Configuration is root/Module context rather than a DI service.

### Removed

- Legacy Router instances and method-bound route decorators.
- Lifecycle decorators, synchronous initialization, `services=`, and config-as-child composition.

## [0.5.1] — 2026-06-15

- Declared the `pydantic-settings` dependency explicitly.

Earlier releases are preserved in Git tags and history.
