# Changelog / 变更日志

This project follows Keep a Changelog and Semantic Versioning.

## [0.9.3] — 2026-09-08

A convergence release: the failure paths are completed, the mental model is straightened out, and
everything that looked necessary but that users can write themselves in ten lines is gone. It
contains several breaking changes — 0.9.x is still taking shape.

一次收敛：补完失败路径、理顺心智模型，并砍掉那些"看起来该有、其实使用者自己十行就能写"的
东西。含多处破坏性变更。

**The rule that runs through it**: the framework only builds empty shells; anything that needs
input from outside happens in the lifecycle. Every instance on the graph is constructed by the
framework with no arguments — there is no second source.

### Added

- **Injection moved from `start()` to `init()`.** `@on_init` therefore has a meaning of its own
  for the first time — "dependencies are in place, nothing is running yet" — and assembly errors
  surface during assembly instead of waiting for `start()`.
- `ConstructionError` — a unit that needs constructor arguments gets an actionable error naming
  the single way out (turn the argument into a dependency), instead of a bare `TypeError` that
  neither points at the rule nor inherits `CanaryError`.
- `DeclarationError` — `@get` on a plain `@cocoa` used to fail silently: the decorator applied,
  nothing was reported, and the route was simply not there. Refused at assembly now.
- `InjectionError` — two dependencies whose snake_case names collide no longer let the last one
  silently win.
- Assembly summary on the `canary.runtime` logger at DEBUG: start order, each unit's
  dependencies, and the mounted routes.
- `CANARY_SLOW_CALLBACK_SECONDS` — an optional event-loop lag probe. It catches synchronous
  blocking inside `async def` bodies, complementing the declaration-time refusal of synchronous
  handlers, and is restored on `stop()` so it never leaks into the rest of the process.
- `status_code` on every route decorator — `@post(..., status_code=201)`,
  `@delete(..., status_code=204)`. Previously this meant building a `Response` by hand, which
  lost both return-type validation and the response schema in the document. `204` / `304` send
  an empty body per the HTTP spec.
- Documentation metadata: `tags` (on `@web_cocoa` and on each route, concatenated), `summary`,
  `deprecated`. The OpenAPI `description` comes from the handler's docstring.
- Return values are validated against the return annotation before serialisation. `/docs`
  promises callers that shape, so a mismatch is a server-side bug and becomes a 500.

### Changed

- **BREAKING: `Canary(provide=...)` removed** (it never shipped under its earlier name
  `overrides=` either). It contradicted "units are always constructed with no arguments":
  `ConstructionError` pointed at it, while `provide` refused any instance that declared `deps`.
  Substituting a dependency in a test is plain attribute assignment (`svc.database = FakeDb()`)
  — injection never did more than that. `ProvisionError` is gone with it.
- **BREAKING: `@on_request_error` and exception-mapping registration removed.** Exceptions now
  have three fixed outcomes: the request cannot bind → 422, `HTTPError` → its own status code,
  anything else → a JSON 500. Expected business failures belong in the return value, not thrown
  for the framework to translate into a status code.
- **BREAKING: prefixes no longer nest along the dependency chain.** `@web_cocoa(prefix=...)` is
  an absolute prefix. Dependencies say what starts first and who may call whom; URLs say how
  resources are named — neither should decide the other. Prefixes are normalised (`"api"`,
  `"/api/"` → `/api`).
- **BREAKING: `Query` / `Path` / `Body` parameter markers removed.** Inference already gives the
  same answer: scalars come from the query string (or the path when the name matches a
  placeholder), everything else from the body. `Header` and `Cookie` stay — they are the only two
  sources inference cannot reach.
- **BREAKING: parameter markers only inside `Annotated`.** `x: int = Query(10)` made the
  default-value position mean two things at once; the form is refused at assembly.
- **BREAKING: handlers and error handlers must be `async def`.** A synchronous handler runs on
  the event loop and stalls the whole process, not just its own request. The framework refuses at
  declaration time rather than silently offloading it to a thread pool; wrap blocking calls with
  `await asyncio.to_thread(...)`.
- **BREAKING: `/redoc` removed.** One documentation UI is enough.
- `stop()` is the single reclamation path — callable from `STARTED` and from `FAILED`, idempotent,
  a no-op when nothing ever started. `finally: await app.stop()` is always safe.
- Core dependencies are back to none: pydantic left the core and belongs to `[web]` only.
- `MissingParameterError` is no longer public: it is an internal signal always wrapped in
  `RequestValidationError`, which is what callers catch.

### Fixed

- **A failing `start()` leaked started units.** It now keeps an explicit ledger and unwinds it in
  reverse (including the unit that failed), then re-raises the original exception with rollback
  failures attached as notes.
- **A failing `@on_stop` aborted the shutdown.** Errors are collected, the remaining units are
  reclaimed anyway, and everything is raised at the end as one `ExceptionGroup`.
- **A failing lifespan startup hung the process.** After sending `lifespan.startup.failed` the
  error must be raised, or a caller that implements the protocol fully concludes an app that
  never started did start, and hangs forever at shutdown. Shutdown failures are handled
  symmetrically.
- **Concurrent cold start without a lifespan crashed.** The check was "is the state NEW", so once
  the first request flipped it to STARTING and yielded, later requests skipped startup and went
  straight to a serving app that did not exist. Five concurrent first requests produced one
  success and four `RuntimeError`s.
- **Every request-body failure became a 500.** `request.json()` raises `JSONDecodeError`, which
  dispatch did not catch. An empty body, invalid JSON and a form post are all 422 now — and
  reading the raw bytes first makes `item: Item | None = None` (an optional body) expressible.
- **Constraints inside `Annotated` were silently dropped.** `Annotated[int, Field(gt=0)]` neither
  validated nor reached the document.
- **Two request-body parameters each received the whole body.** Refused at assembly.
- **`prefix="api"` raised a bare `AssertionError`** from Starlette. Route paths were already
  normalised; prefixes now are too.
- **One undescribable type took down the whole OpenAPI document.** It degrades to an
  unconstrained schema and logs a WARNING naming the handler — at startup, not on the first
  request for the document.
- **`{name:path}` converters leaked into the OpenAPI document.**
- **Handlers could not return a `Response`.** SSE, file downloads, custom status codes and
  background tasks all work now.
- **A validator raising `ValueError` crashed its own 422** into a 500 (the live exception object
  sat in `ctx` and could not be serialised).
- **Non-scalar parameters were read from the query string.**
- **The slow-callback probe could not see the startup phase.** asyncio reads the debug flag
  before a callback runs, and the probe was switched on inside `init()` — so init and start,
  which usually run in that same callback, were never measured.

### Performance

- Handler signatures are compiled at assembly time into a value-fetching plan (source, validator,
  default, serialiser). The request path no longer re-runs `get_type_hints`, rebuilds
  `inspect.signature` or constructs `TypeAdapter`s: **125 µs → 16.5 µs** per request on the
  framework's own path (direct ASGI call, mean of 20 000).
- Dispatch and OpenAPI generation read the same plan, so the documented binding behaviour and the
  actual behaviour cannot drift apart.
- The MRO scan behind lifecycle hooks and routes is a single implementation, cached per class.

### Removed

- `SERVE_ATTR` and `ROUTE_ENTRIES_ATTR` — `@web_cocoa` no longer injects a hook to stash route
  entries on the instance for `Canary` to read back. It only writes a marker; `Canary` picks the
  units carrying it and hands them to the web extension.
- `runtime/mounts.py` — with absolute prefixes the runtime does no path arithmetic at all.
- `build_web_app` — dead, and a second entry point for what `build_serve_app` already did.
- The re-export layers in seven `__init__.py` files that had no callers (and had already drifted:
  `common/__init__` forwarded three of six errors).

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
