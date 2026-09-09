# Changelog / 变更日志

This project follows Keep a Changelog and Semantic Versioning.

## [0.9.3] — 2026-09-09

A convergence release: it pulls the framework back to the one thing it is actually different at —
**dependency assembly and lifecycle** — and completes the failure paths. Several breaking
changes, the largest of which is that the entire web extension is gone.

一次收敛：把框架收回到它真正差异化的那一件事上——依赖装配与生命周期——并补完失败路径。
含多处破坏性变更，最大的一条是删掉了整个 web 扩展。

**What it is now**: Canary is a runtime container, not a web framework. It assembles objects by
their dependencies, starts them in order and reclaims them in reverse; what shell drives them
(HTTP, a CLI, a scheduler, a message consumer) is that shell's business. Plugging it into a host
is one line — `async with canary:`.

### Removed

- **`canary_framework.web` — the entire extension** (`@web_cocoa`, route decorators, parameter
  binding, OpenAPI generation; ~1300 lines), together with **`Canary`'s ASGI surface**
  (`__call__`, the lifespan protocol, cold start with its concurrency lock, route collection;
  ~100 lines). `Canary` is no longer an ASGI app.

  Not because it was bad — its request path measured 2.4–3.3× faster than FastAPI at the ASGI
  level. Because it was not our job: it did what FastAPI and Starlette already do, it forced a
  permanent chase after WebSocket / uploads / middleware / auth, it was more than half the code,
  and it produced nearly all of the bugs.

  And the one thing it was protecting does not need it. "Routes are methods on a
  dependency-injected unit" works by handing the bound method to FastAPI directly — a bound
  method's signature has no `self`, so FastAPI binds, validates and documents it as usual, while
  `self.repo` is already there because Canary assembled the instance:

      unit = canary[LibraryApi]                    # a plain @cocoa, no web markers
      app.get("/books/{book_id}")(unit.get_book)   # FastAPI takes it as-is

- `Canary(provide=...)` and `ProvisionError` — they contradicted "units are always constructed
  with no arguments". Substituting a dependency in a test is plain attribute assignment
  (`svc.database = FakeDb()`); injection never did more than that.
- `DeclarationError`, the ASGI type aliases in `common.type`, and the `ROUTE_ATTR` / `WEB_ATTR`
  markers — every one of them existed only for the web layer.
- The `[web]` and `[test]` extras. The package now has no optional runtime dependencies at all.
- The re-export layers in seven `__init__.py` files that had no callers (and had already drifted:
  `common/__init__` forwarded three of six errors).

The framework went from ~2300 lines to **842**, and every remaining line does dependency
assembly or lifecycle.

### Added

- **Injection moved from `start()` to `init()`.** `@on_init` therefore has a meaning of its own
  for the first time — "dependencies are in place, nothing is running yet" — and assembly errors
  surface during assembly.
- `ConstructionError` — a unit that needs constructor arguments gets an actionable error naming
  the single way out (turn the argument into a dependency), instead of a bare `TypeError` that
  neither points at the rule nor inherits `CanaryError`.
- `InjectionError` — two dependencies whose snake_case names collide no longer let the last one
  silently win.
- Assembly summary on the `canary.runtime` logger at DEBUG: start order and each unit's
  dependencies.
- `CANARY_SLOW_CALLBACK_SECONDS` — an optional event-loop lag probe that catches synchronous
  blocking inside `async def` bodies, restored on `stop()` so it never leaks into the rest of the
  process.

### Changed

- **BREAKING: `stop()` is the single reclamation path** — callable from `STARTED` and from
  `FAILED`, idempotent, a no-op when nothing ever started. `finally: await app.stop()` is always
  safe.
- Core dependencies are none, and a test guards it: after a full lifecycle, nothing from
  site-packages may appear in `sys.modules`.

### Fixed

- **A failing `start()` leaked started units.** It now keeps an explicit ledger and unwinds it in
  reverse (including the unit that failed), then re-raises the original exception with rollback
  failures attached as notes.
- **A failing `@on_stop` aborted the shutdown.** Errors are collected, the remaining units are
  reclaimed anyway, and everything is raised at the end as one `ExceptionGroup`.
- **A dependency chain of ~1000 hit `RecursionError`.** How deep a chain goes is the user's data,
  not something Python's recursion limit should bound — and `RecursionError` is neither in the
  framework's error hierarchy nor informative. The graph is now built with an explicit stack
  (same depth-first visit order); 50 000 links work fine.
- **The slow-callback probe could not see the startup phase.** asyncio reads the debug flag
  before a callback runs, and the probe was switched on inside `init()` — so init and start,
  which usually run in that same callback, were never measured.

### Performance

- **Assembly is 15.6× faster**: `inspect.signature` sat on the success path while existing only
  to explain failures. Construction now calls first and inspects the signature only after a
  `TypeError`, which still tells an arity problem (`ConstructionError`) apart from an error
  raised by the constructor itself (propagated unchanged). 1000 units: 37.7 ms → 2.4 ms.
- **The MRO scan is 11× faster**: `object` is skipped — it has two dozen callable members, none
  of which can carry our markers, and it sits at the end of every MRO. Self time over 5000 units:
  55 ms → 5 ms. The scan itself is one implementation, cached per class.
- `deps_of` returns the stored tuple instead of copying it on every call.
- The framework's own modules cost **0.0 ms** to import; a 1000-unit graph is ~3.9 MiB.

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
