# Changelog / 变更日志

This project follows Keep a Changelog and Semantic Versioning.

## [0.9.3] — 2026-09-04

修复两条失败路径上的全部已知问题，并给单元补上「配置」与「日志」两个协作者。
This release closes the framework's failure paths — request handling and lifecycle — and
gives every unit its logger and its settings.

### Added

- `@on_request_error(ExcType, ...)` — map an exception to a response, once, for the whole
  app. Structurally identical to `@get` (a method marker read at assembly), looked up by
  `type(exc).__mro__`. Registering the same type twice raises `RouteRegistrationError`.
- `HTTPError(status_code, detail, headers=)` — for errors that already *are* HTTP concepts;
  no registration needed. Domain errors should stay domain errors and be mapped instead.
- `RequestValidationError` — 422 is now *raised* rather than returned, so it can be replaced
  with the house error envelope via `@on_request_error(RequestValidationError)`.
- Built-in handlers for `RequestValidationError` (422), `HTTPError`, and `Exception`
  (a JSON 500). All three are overridable.
- `Canary(*roots, overrides={Type: substitute})` — replace a unit (or a config class) with a
  ready-made instance. Substitution happens at *construction*, so an overridden unit's own
  dependencies are never instantiated. An override that never applies raises `OverrideError`.
- Class-level annotations are declarations the runtime fills: `log: logging.Logger` gets a
  logger named `module.QualName`; `config: SomeSettings` gets the shared instance of that
  settings class. Two sources claiming the same attribute name raise `InjectionError`.
- `canary_framework.common.config` — `Config` (a `BaseSettings` that also reads `.env`) and
  `CanaryConfig` (`CANARY_*`; `log_level` applies to the `canary` logger tree only).
- Assembly summary on the `canary.runtime` logger at DEBUG: start order, dependencies,
  substitutions, mounted routes, error handlers — plus a note when multiple roots mean there
  is no "after everything started" position.

### Fixed

- **Start failure leaked started units.** `start()` now keeps an explicit ledger and unwinds
  it in reverse (including the unit that failed), then re-raises the original exception with
  rollback failures attached as notes.
- **A failing `@on_stop` aborted shutdown.** Stop now collects errors and keeps going,
  raising an `ExceptionGroup` at the end.
- **`stop()` was illegal after a failure.** It is now callable from any settled state and is
  idempotent — one reclamation path for both normal and failed termination.
- **Lifespan startup failure hung the process.** `_lifespan` returned to `await receive()`
  after sending `lifespan.startup.failed`, where no further message ever arrives.
- **A validator raising `ValueError` crashed its own 422** into a 500 (the live exception
  object sat in `ctx` and could not be serialised).
- **Handlers could not return a `Response`.** SSE, file downloads, custom status codes and
  background tasks all work now.
- **Non-scalar parameters were read from the query string.** Inference is now one rule:
  scalars come from the query (or the path when the name matches a placeholder), everything
  else from the body.
- **One undescribable type took down the whole OpenAPI document.** It degrades to an
  unconstrained schema with a WARNING naming the handler.
- **`{name:path}` converters leaked into the OpenAPI document.**

### Changed

- **Handlers must be `async def`.** A synchronous handler runs on the event loop and stalls
  the entire process, not just its own request; Canary refuses to route it at declaration
  time rather than silently offloading it to a thread pool. Wrap blocking calls with
  `await asyncio.to_thread(...)` — one rule, and it works in handlers, repositories and
  lifecycle hooks alike. `@on_request_error` handlers follow the same rule.
- `stop()` raises `ExceptionGroup` instead of the first exception.
- Unhandled exceptions produce a JSON 500 body instead of Starlette's `text/plain`.
- `pydantic` and `pydantic-settings` are now core dependencies (`dependencies` is no longer
  empty). Configuration is not an optional concern the way `web` is — every application has
  it — so making it an extra would have meant a core feature that sometimes isn't there.
  The `web` extra drops its own `pydantic` entry.

### Notes

- **Multiple roots have no "after everything started" position.** With a single root, that
  root is always last in topological order, so its `@on_start` *is* the after-all hook and
  its `@on_stop` runs before anything else tears down. Declare a composition root when you
  need it; no new lifecycle hook was added.
- Acquire resources in `@on_start`, not `@on_init` — dependencies are not injected yet at
  init time, so an `@on_stop` written against them has nothing to release.
- `@on_stop` must tolerate a unit whose `@on_start` only got halfway; that is the price of
  rolling back the failed unit too.

## [0.9.2] — 2026-08-19

### Added

- Nested routers — `@web_cocoa(prefix="/api", deps=[AdminRouter])` now mounts `AdminRouter`'s
  routes *under* `/api`. Prefixes chain along the dependency edges (plain `@cocoa` units in
  between are skipped), computed by the new pure `canary_framework.runtime.mounts` module.
  A unit reached by several dependency paths keeps its single instance but mounts once per
  path (`/a/c` and `/a/b/c` hit the same object); identical prefixes mount only once.
- `prefix=` on `@web_cocoa` — a common path prefix for all of the unit's routes.

### Changed

- `Canary` now merges the routes of **all** `@web_cocoa` units into one Starlette app with a
  single `/openapi.json` / `/docs` / `/redoc`, instead of serving the first unit that exposed
  an app. `title` / `version` come from the outermost (root-most) web unit. With a single
  `@web_cocoa`, behaviour is unchanged. Route collisions across units raise
  `RouteRegistrationError` at startup — the message now names both colliding units.

### Removed

- `SERVE_ATTR` — no longer written or read. `Canary` merges route entries itself (importing
  the web builder lazily, only when routes exist), so the marker had no reader left.

## [0.9.1] — 2026-08-18

### Fixed

- Router / hook introspection no longer silently drops same-named methods across mixins.
  `routes_of` / `hooks_of` now read each class's own `__dict__` entry and de-duplicate by
  function identity (instead of method name), so `KB.create` / `File.create` / `Coll.create`
  all keep their own routes. Scanning no longer triggers Pydantic instance-attribute
  deprecation warnings either.

### Added

- New optional dependency `canary-framework[test]` (`httpx2>=2.10`) for Starlette 1.x's
  `TestClient`, plus an in-process testing guide in the English and Chinese web docs.

## [0.9.0] — 2026-08-15

### Added

- `canary_framework.web` extension — expose `@cocoa` services as an ASGI app (FastAPI-style).
  - `@web_cocoa(deps=[...], title=..., version=...)` — mark a class as a `@cocoa` *and* an
    HTTP route holder; a plain `Canary(*roots)` collects its `@get`/`@post`/… routes and
    serves them, so `uvicorn app:app` just works (`app = Canary(LibraryAPI)`).
  - Route decorators `@get` / `@post` / `@put` / `@patch` / `@delete` / `@route`.
  - Auto-injection: path / query / header / cookie / body (Pydantic model) parameters are
    bound by name from the request, plus `request: Request` injection; cocoa dependencies
    remain on `self.<dep>`.
  - Pydantic v2 validation for request bodies and responses (scalar coercion via
    `TypeAdapter`; validation failures map to HTTP 422).
  - Auto OpenAPI 3.1 document at `/openapi.json`, Swagger UI at `/docs`, Redoc at `/redoc`.
- New optional dependency `canary-framework[web]` (starlette + pydantic + uvicorn).

### Changed

- Extracted the runtime engine (`Canary`) out of `core` into a new `canary_framework.runtime`
  package. `Canary` now implements the ASGI protocol directly: it drives the lifecycle on
  `lifespan` and, for every other scope, delegates to a serving app that a unit exposed during
  `start()` — found by duck typing on the shared `SERVE_ATTR` marker, without `Canary` importing
  any concrete extension.
- Centralised all metadata markers in `canary_framework.common.markers` (`COCOA_ATTR`,
  `ON_INIT` / `ON_START` / `ON_STOP`, `SERVE_ATTR`, `ROUTE_ATTR`, `WEB_ATTR`), grouped by
  subsystem, so every layer shares one contract with no magic-string drift.

## [0.8.0] — 2026-08-15

### Breaking: 从 `@canary`/`Flock` 迁移到 `@cocoa`/`Canary`

0.8.0 replaces the 0.7.0 `@canary` / `Flock` model with `@cocoa` / `Canary`, an explicit
async-native lifecycle, and lazy dependency injection.

| 0.7.0 | 0.8.0 |
|---|---|
| `@canary` | `@cocoa(deps=[...])` |
| `__init__(database: Database)` | `@cocoa(deps=[Database])` |
| `@start` / `@stop` | `@on_start` / `@on_stop`（外加 `@on_init`） |
| `Canary.run()` / `Flock` | `Canary(*roots)` |
| `await flock.start()` | `await app.init(); await app.start()` |
| `async with X.run() as flock` | `async with Canary(X) as app` |

### Added

- `@cocoa(deps=[...])` — 标记最小单元；依赖在 `start()` 阶段惰性注入为 snake_case 属性。
- `@on_init` / `@on_start` / `@on_stop` 钩子，同步/异步皆可，每阶段可叠加多个。
- `Canary(*roots)` 编排器：多根、显式 `init()` / `start()` / `stop()`、共享单例。

### Removed

- `Flock`、`Canary.run()`、`FlockState`，以及基于 `__init__` 注解的依赖声明。

## [0.7.0] — 2026-08-15

### Breaking: 移除 web 层，改为 Canary / Flock 引擎

0.7.0 removes the Service / Router / Module web layer entirely and replaces it with a pure
Canary / Flock lifecycle and dependency-injection engine. There is no 0.6.x compatibility layer.

| 0.6.0 | 0.7.0 |
|---|---|
| `@service()` / `ServiceBase` | `@canary` |
| `@router()` / `RouterBase` | removed |
| `@module()` / `ModuleBase` | removed |
| `@get` / `@post` / … | removed |
| `on_init` / `on_startup` / `on_shutdown` | `@start` / `@stop` |
| `await app.init()` + ASGI lifespan | `Canary.run()` + `await flock.start()` |
| config service | `@canary class Config` |
| OpenAPI / docs endpoints | removed |

### Added

- `@canary` decorator turning a plain Python class into a Canary.
- Dependency injection through `__init__` type annotations — no DSL.
- `@start`, `@stop` lifecycle hooks (0..1 per stage per Canary).
- `Flock` orchestrator (via `Canary.run()`): dependency discovery, topological sort, singleton-per-graph instances, startup rollback, and reverse-order shutdown.
- Standalone usage through the native async context-manager protocol (`async with canary`).
- Explicit state machines: `LifecycleState` (per Canary) and `FlockState` (per Flock).

### Removed

- The entire web layer: `RouterBase`, `ModuleBase`, `ServiceBase`, routing decorators, OpenAPI generation, and the configuration system.

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
- Folded the unreleased 0.5.2 Router redesign into this release: one memoized assembly produces one Starlette route table, one OpenAPI document, and documentation endpoints from resolved routes; scattered aggregation and standalone/mounted branches were removed.
- Strict dependency direction, parent reuse, sibling isolation, and explicit promotion.
- Root-owned OpenAPI compilation with local schema registries and conflict detection.
- Explicit async lifecycle states: `CREATED`, `INITIALIZED`, `STARTED`, `STOPPED`, `FAILED`.

### Fixed / 修复

- OpenAPI schema generation uses a local registry per document, preventing stale `$ref` values across repeated builds.
- Request binding consistently uses parameter names, including path parameters combined with request bodies.
- Missing required query parameters and invalid boolean query values now return 422 instead of 500; boolean parsing accepts `1/true/yes/on` case-insensitively.
- `(body, status_code)` handler returns preserve the tuple status instead of being stringified with the route default.

### Changed

- `await app.init()` is mandatory; lifespan only starts and stops an initialized root.
- Services are lifecycle/DI/domain objects and are never served directly.
- Modules cannot own business endpoints; they aggregate Router descendants.
- Configuration is root/Module context rather than a DI service.
- Explicit Router prefixes replace the old implicit `/{ServiceName}` namespace; route conflicts fail during compilation. The unreleased 0.5.2 memoized `ServiceBase.openapi()` experiment is superseded: OpenAPI is now exposed only by an initialized runtime-root Router or Module.

### Removed

- Legacy Router instances and method-bound route decorators.
- Lifecycle decorators, synchronous initialization, `services=`, and config-as-child composition.

## [0.5.1] — 2026-06-15

- 显式声明 `pydantic-settings` 依赖（`BaseSettings` / 配置类）。

## [0.5.0] — 2026-06-15

- 配置系统与核心优化；router 重构。

## [0.4.11] — 2026-06-05

- 底层优化：要求通过类型注解继承基类；修复 router 相关缺陷；推出独立配置类。

## [0.4.0] — 2026-05-31

- **ASGI 集成、移除独立 web 包的大重构**：框架从 FastAPI 迁移到直接的 ASGI（Starlette）集成，
  重新设计模块启动生命周期。`0.4.x` 后续版本持续打磨依赖注入体验与日志能力。

## [0.3.0] — 2026-05-27

- 移除 Context 系统，改为基于类型注解的依赖注入；统一以 config 承载生命周期配置。

## [0.2.0] — 2026-05-25

- 发布流程与分支规范调整。

## [0.1.0] — 2026-05-25

- 首个开源版本：README、文档、社区文件与 CI/CD。

---

## 版本策略 / Versioning Policy

0.6.0 已因 Service/Router/Module 核心模型的根本变化推进版本线。今后遵循语义化版本：在 0.x
阶段，破坏性设计变化推进 minor 版本；补丁修复与兼容特性在对应版本线上发布。

0.6.0 advances the version line because the Service/Router/Module core model changed fundamentally.
From here, releases follow Semantic Versioning: while the project remains in 0.x, breaking design
changes advance the minor version, while fixes and compatible features ship on the corresponding line.
