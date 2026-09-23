# Changelog / 变更日志

This project follows Keep a Changelog and Semantic Versioning.

## [Unreleased]

## [1.0.1] — 2026-09-23

### Fixed

- `stop()` called while `start()` is still running waits for it to finish before reclaiming.
  It used to run `@stop` first; the in-flight `@start` then acquired its resource after
  reclamation, and nothing released it. The same applies to `unwind()` for any phase.
  ([#10](https://github.com/HotcocoaCanary/Canary-Framework/issues/10))

  `start()` 仍在进行时调用 `stop()`，会先等它结束再回收，不再泄漏在回收之后才获取的资源。

### Documentation

- Patterns: blocking work in hooks (`asyncio.to_thread`), and bounding shutdown with
  `asyncio.timeout`. ([#11](https://github.com/HotcocoaCanary/Canary-Framework/issues/11))

  常见用法：钩子里的阻塞操作与限时关闭。

### Packaging

- The source distribution lists its contents explicitly — `src`, `tests`, the READMEs, the
  changelog and the license — so the `examples/` submodule and the docs are no longer packed
  into it. The wheel is unchanged.

  sdist 显式列出所含内容，不再打入 `examples/` 子模块与文档；wheel 不变。

### Examples

- `examples/` is now a submodule of
  [Canary-Framework-Example](https://github.com/HotcocoaCanary/Canary-Framework-Example) — a
  FastAPI service with RAG and a long-running telemetry daemon, both on 1.0 — replacing the
  in-repository library example. Run `git submodule update --init` to fetch it. An existing
  clone that still has the old `examples/` files may need them removed before switching to a
  branch with the submodule. ([#12](https://github.com/HotcocoaCanary/Canary-Framework/issues/12))

  `examples/` 改为 Canary-Framework-Example 子模块（FastAPI + RAG 服务与常驻遥测守护进程）。
  用 `git submodule update --init` 拉取；旧 clone 若残留原 `examples/` 文件，切换分支前需先删除。

## [1.0.0] — 2026-09-23

The first stable release. The core introduced in 0.10 is kept; from here on the public API
follows Semantic Versioning — no breaking changes before 2.0, and removals are deprecated for at
least one minor release first. See the
[versioning policy](https://hotcocoacanary.github.io/Canary-Framework/versioning/).

第一个稳定版本，沿用 0.10 引入的核心。自此公开 API 遵循语义化版本：2.0 之前不做破坏性变更，
任何移除都至少提前一个次版本弃用。

Upgrading from 0.10: replace `service.dep = Fake()` with `scope_of(service).provide(Dep, Fake())`,
and iterate `scope.entered[phase].values()`. Upgrading from 0.9.x: see
[Upgrading from 0.9.x](https://hotcocoacanary.github.io/Canary-Framework/upgrading-from-0.9/).

### Added

- `Scope.provide(cls, unit)` replaces a dependency across the whole graph: every `dep(cls)`
  returns `unit`, which runs its own hooks and advances the dependencies its own type
  declares. `Scope.resolve(cls)` returns the type standing in for `cls`.

  `Scope.provide(cls, unit)` 在整张图上替换一个依赖：所有 `dep(cls)` 都取回 `unit`，它运行
  自己的钩子，推进自身类型声明的依赖。

### Changed

- **BREAKING: `Scope.entered[phase]` is a `dict[type, object]`**, keyed by the type that was
  advanced, instead of a list. A unit that re-enters a phase keeps a single entry.
- Assigning to a dependency attribute raises `AttributeError` pointing to `provide()`. It used
  to replace that one attribute silently while the rest of the graph kept the original.

### Fixed

- A stopped graph can start again. `stop()` left the `start` records in place, so a second
  `start()` returned without running anything. It now undoes `start`, and every phase declared
  after it, for each unit it reclaims; `@init` is not rerun.
- A failed or cancelled advance can be retried. The failure used to be cached, so every later
  call re-raised the first exception without running anything.
- `start()` after a failed `init()` raises `LifecycleError` instead of proceeding, because the
  failed `init` no longer counts as completed.

  停止的图可以再次启动；失败的推进可以重试；`init()` 失败之后调用 `start()` 会抛
  `LifecycleError` 而不是继续执行。

### Documentation

- New pages: What's New in 1.0, Patterns (test doubles, choosing an implementation from
  configuration, hosting, retry), Versioning & Compatibility, Contributing and Governance.
  The 0.10 release notes became "Upgrading from 0.9.x".

  新增页面：1.0 新特性、常见用法、版本与兼容性、贡献指南与项目治理；中文站导航完成翻译。

### Infrastructure

- Releases are triggered by pushing a `vX.Y.Z` tag instead of a `releases/v*` branch; PyPI
  publishing requires approval in the `publish` environment. CI type-checks tests, builds the
  docs strictly, requires 95% coverage and checks PR titles against Conventional Commits.

  发布改为推送 tag 触发，PyPI 发布需在 publish 环境审批；CI 增加文档严格构建、PR 标题检查，
  覆盖率门槛提高到 95%。

## [0.10.0] — 2026-09-14

A complete rewrite of the core. Not compatible with 0.9.x; there is no compatibility layer.

核心完全重写。与 0.9.x 不兼容，且没有兼容层。

### Changed

- **BREAKING: a unit is a base class, not a decorator.** `@cocoa` is gone; subclass `Canary`
  instead. The unit itself carries the lifecycle — `init()`, `start()`, `stop()` and
  `async with unit` — so `svc.init()` and `self.config` are visible to type checkers and IDEs,
  which a decorator cannot achieve.
- **BREAKING: dependencies are declared with `dep()`, not `deps=[...]`.** `database =
  dep(Database)` is a descriptor: the attribute name is the user's choice rather than the
  snake_case of the class name, the type is inferred with no extra annotation, and the
  declaration holds the class object itself so it never needs evaluating (unaffected by
  `from __future__ import annotations`, `if TYPE_CHECKING` or function-local classes).
- **BREAKING: hooks are `@init` / `@start` / `@stop`**, instances of the public `Phase` class.
  They are both the decorators and the engine's arguments; `Phase("migrate", after=init)` adds
  a fourth phase with no registration.
- **BREAKING: hooks resolve by attribute name.** Overriding a hook replaces it, and `super()`
  composes — matching ordinary method semantics. 0.9.x deduplicated by function identity, which
  turned an override into an addition.
- **BREAKING: one scope is one graph.** Two separately constructed roots are two unrelated
  graphs; even shared dependencies are distinct instances.
- `stop()` is a graph action: it reclaims the whole scope's ledger, so calling it on any unit
  in the graph has the same effect. Reclamation cannot be divided because a dependency graph is
  not a tree.
- Concurrency is the default. Independent dependencies advance together, scheduled by
  dependency; there is no longer anything to configure.

### Added

- `Phase`, `advance()` and `unwind()` as the public engine: `advance` recurses along
  dependencies, `unwind` drains a ledger in reverse. Custom phases pair with a reclamation
  phase at the call site: `unwind(scope, rollback, undoing=migrate)`.
- `Scope`, `scope_of()` and `deps_of()` for inspecting a run.
- `DeclarationError` — `dep()` rejects a non-unit while the class body is evaluated; type
  checkers reject it too, because `dep()`'s type parameter is bound to `Canary`.
- `tests/test_layering.py` — the layering `canary → runtime → declare → errors` is asserted by
  parsing every module's imports, so a reverse dependency fails the test suite.

### Fixed

- **A dependency chain of about 493 units raised `RecursionError`.** A single dependency is
  still awaited directly, but every 32 levels the call stack is handed back to the event loop;
  5000 levels are covered by a test.
- **Cycle detection is no longer on the hot path.** A cycle is exactly a unit that has not
  finished and sits on the current path, so the check happens only on an unfinished memo hit.
  This removes a quadratic term: a 3000-deep chain goes from 213ms to 163ms.
- **`async with` now goes through the unit's own lifecycle methods**, so a subclass overriding
  `start()` applies on that path as well as on the explicit one.

### Removed

- `@cocoa`, the `Canary(*roots)` runtime container, `canary.order`, `canary.instances`,
  `canary[Type]`, `canary.lifespan`, `start_concurrency=`, the assembly summary and
  `CANARY_SLOW_CALLBACK_SECONDS`.
- `LifecycleState` and the eight-state machine. "Not started / in progress / finished" is
  expressed by the advance record itself.
- The standalone topological sort. Depth-first plus memoisation already produces a valid
  topological order.
- snake_case-by-class-name injection, class-level annotation injection, and `Config` / logger
  injection.
- `tmp/` (0.9.3 field reports), `tests/conftest.py`, the `cocoa.md` documentation page and the
  stale `--extra web` reference in `CONTRIBUTING.md`.

### Performance

Measured in isolated processes, best of five:

      fan(1000)      14.2 ms     one root with 1000 independent leaves
      diamond(12)     7.3 ms     6 layers x 12 wide, fully connected, 864 edges
      chain(300)      3.4 ms
      chain(3000)   163.4 ms

Source is 773 lines across 13 modules with 16 public names; 44 tests, 99% coverage.

## [0.9.3] — 未发布 / never released

Developed but never published. Its work is superseded by 0.10.0; the entry is kept for the
record.

开发完成但从未发布，内容已被 0.10.0 取代，此处仅作记录。

### Changed

- **BREAKING: assembly moved into the constructor.** `Canary(*roots)` builds the graph, sorts it
  topologically and injects dependencies — synchronously, with no event loop, running no hooks.
  When it returns, `canary[SomeUnit]` works. Every assembly error (`ConstructionError`,
  `InjectionError`, `CircularDependencyError`, `TypeError` for a non-cocoa) is raised on that
  line rather than at a later `await`.
- **BREAKING: each lifecycle method runs exactly one hook phase.**

      await canary.init()     every @on_init
      await canary.start()    every @on_start, ledgered on entry
      await canary.stop()     every @on_stop, in reverse

  Between `init()` and `start()` is a barrier: every `@on_init` completes before any `@on_start`
  runs. Calling `start()` from `READY` raises `LifecycleError: call init() before start()`.
  `async with canary` and `canary.lifespan` remain the convenience path that does all of it.
- **BREAKING: `LifecycleState.NEW` renamed `READY`.**
- **BREAKING: `stop()` is the single reclamation path** — callable from `STARTED` and from
  `FAILED`, idempotent, a no-op when nothing ever started. One rule replaces the previous two:
  `stop()` reclaims whatever is in the ledger. The ledger records units that entered
  `@on_start`; a failure during `init()` leaves it empty.
- **BREAKING: handlers, markers and everything else in `canary_framework.web` are gone** (see
  *Removed*).
- `deps_of()` returns a tuple instead of a list.
- The event-loop probe now switches on inside `init()`, covering both hook phases.
- Core dependencies are none; a test asserts that a full lifecycle imports nothing from
  site-packages.

### Added

- **`Canary(*roots, start_concurrency=N)`** — independent units start together, at most N at
  once. Scheduling is dependency-driven, so elapsed time tracks the graph's critical path
  (measured: 3009ms → 423ms on 50 independent 60ms units; 260ms → 152ms on a typical web shape;
  unchanged on a chain). The default, `None`, is strictly sequential. Failure semantics match
  sequential startup: siblings are cancelled and still reclaimed, a lone failure is re-raised
  as-is, several simultaneous failures become an `ExceptionGroup`.
- **`Canary.lifespan`** — the host-facing entry point, shaped as
  `Callable[[Host], AsyncContextManager[None]]`: ASGI's `lifespan=` (Starlette, FastAPI,
  Litestar), MCP's `MCPServer(lifespan=)`, FastStream's `lifespan=`. It yields `None`, which the
  ASGI lifespan protocol requires (the yielded value is merged into `scope["state"]`);
  `async with canary` still hands back the container.
- `ConstructionError` — an actionable error when a unit needs constructor arguments.
- `InjectionError` — raised when two dependencies produce the same snake_case attribute name.
- The assembly summary on the `canary.runtime` logger at DEBUG: start order, each unit's
  dependencies and timing, plus a `start_concurrency` suggestion computed from the critical path.
- `CANARY_SLOW_CALLBACK_SECONDS` — an event-loop lag probe that catches synchronous blocking
  inside `async def` bodies; restored on `stop()`.

### Fixed

- **A failing `start()` leaked started units.** It now keeps an explicit ledger, unwinds it in
  reverse (including the unit that failed) and re-raises the original exception with rollback
  failures attached as notes.
- **A failing `@on_stop` aborted the shutdown.** Errors are collected, the remaining units are
  reclaimed, and everything is raised at the end as one `ExceptionGroup`.
- **A dependency chain of about 1000 units raised `RecursionError`.** The graph is built with an
  explicit stack; 50 000 links work.
- **The slow-callback probe could not see the startup phase.** asyncio reads the debug flag
  before a callback runs, so the probe now yields once after switching it on.
- **A failing lifespan startup hung the process** (in the web extension, since removed).

### Removed

- `canary_framework.web` — the whole extension (`@web_cocoa`, route decorators, parameter
  binding, OpenAPI generation) and `Canary`'s ASGI surface (`__call__`, the lifespan protocol,
  cold start, route collection). `Canary` is no longer an ASGI app.
- `Canary(provide=...)` and `ProvisionError` — substituting a dependency in a test is plain
  attribute assignment.
- `DeclarationError`, the ASGI type aliases in `common.type`, and the `ROUTE_ATTR` / `WEB_ATTR`
  markers.
- The `[web]` and `[test]` extras; the package has no optional runtime dependencies.
- Re-export layers in seven `__init__.py` files that had no callers.

### Performance

- Assembly is 15.6x faster: `inspect.signature` moved off the success path — construction calls
  first and inspects the signature only after a `TypeError`, which still distinguishes an arity
  problem (`ConstructionError`) from an error raised by the constructor itself. 1000 units:
  37.7ms → 2.4ms.
- The MRO scan is 11x faster (`object` is skipped) and cached per class: 55ms → 5ms over 5000
  units.
- The framework's own modules cost 0.0ms to import; a 1000-unit graph is about 3.9 MiB.

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
