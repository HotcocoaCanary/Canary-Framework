# API Reference

Everything below is exported from `canary_framework` unless stated otherwise.

## `cocoa`

```python
def cocoa(cls=None, *, deps: list[type] | None = None)
```

Marks `cls` as a cocoa — the minimum unit. `deps` is an ordered list of dependency types. Usable
directly or as a decorator factory:

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...
```

Units are always constructed by the framework **with no arguments**: `__init__` may not have
required parameters, or `init()` raises `ConstructionError`.

## `on_init` / `on_start` / `on_stop`

```python
def on_init(fn) -> fn
def on_start(fn) -> fn
def on_stop(fn) -> fn
```

Register a method as a lifecycle hook. Each accepts sync or async functions; a phase may have any
number of hooks, and mixin hooks run before the class's own.

## `Canary`

```python
class Canary(*roots: type)
```

The orchestrator. Raises `TypeError` if a root is not marked with `@cocoa`. Construction itself
does nothing.

### Properties

| Property | Type | Meaning |
|---|---|---|
| `state` | `LifecycleState` | current lifecycle state |
| `order` | `tuple[type, ...]` | topological start order (dependencies first) |
| `instances` | `tuple[object, ...]` | the instances in that order |
| `roots` | `tuple[type, ...]` | the roots given at construction |

### `__getitem__`

```python
def __getitem__(self, cls: type[T]) -> T
```

Returns the shared singleton for `cls`, or raises `KeyError`.

### `init`

```python
async def init(self) -> None
```

`NEW → INITIALIZED`. Builds the graph (each type constructed once, with no arguments), validates,
sorts, **injects dependencies** and runs `@on_init` in order. On failure the state becomes
`FAILED` and the exception propagates — **without unwinding**, since no `@on_start` has run yet.

### `start`

```python
async def start(self) -> None
```

`INITIALIZED → STARTED`. Runs `@on_start` in order, then merges every `@web_cocoa` unit's routes
into one serving app. If any step fails, every unit that entered `@on_start` (including the one
that failed) is reclaimed in reverse, and the original exception is re-raised with any unwind
failures attached as notes.

### `stop`

```python
async def stop(self) -> None
```

Runs `@on_stop` in reverse topological order. **The single reclamation path**: callable from
`STARTED` and from `FAILED`, idempotent, a no-op when nothing ever started. A failing `@on_stop`
does not abort the rest — the errors are collected and raised together as an `ExceptionGroup`.

### `__call__` — ASGI

```python
async def __call__(self, scope, receive, send) -> None
```

Serves ASGI: `lifespan` drives the lifecycle, every other scope is delegated to the merged serving
app. Without a lifespan the first request starts the app, and concurrent first requests queue for
that single startup.

### `__aenter__` / `__aexit__`

The async context manager protocol, wrapping `init()` + `start()` / `stop()`.

## Enums

### `LifecycleState`

`NEW`, `INITIALIZING`, `INITIALIZED`, `STARTING`, `STARTED`, `STOPPING`, `STOPPED`, `FAILED`.

### `State`

(`canary_framework.common.type`) The base of every state enum; a mounting point for `issubclass`
checks.

## Exceptions

| Exception | Base | Meaning |
|---|---|---|
| `CanaryError` | `Exception` | the root of every framework and extension error |
| `CircularDependencyError` | `CanaryError` | a cycle in the graph; `.cycle` lists the type names |
| `ConstructionError` | `CanaryError` | the unit needs constructor arguments and cannot be built |
| `DeclarationError` | `CanaryError` | a declaration sits where nothing reads it (e.g. `@get` on a plain `@cocoa`) |
| `InjectionError` | `CanaryError` | two dependencies claim the same attribute; `.attribute` / `.claimants` |
| `LifecycleError` | `CanaryError` | an illegal lifecycle transition |

Everything inherits `CanaryError`, so a single `except CanaryError` catches the framework and all
its extensions.

## Environment variables

| Variable | Effect |
|---|---|
| `CANARY_LOG_LEVEL` | the level of the `canary` logger tree; `DEBUG` also prints the assembly summary |
| `CANARY_SLOW_CALLBACK_SECONDS` | threshold in seconds for the event-loop lag probe; a development tool, off by default |

## Introspection (`canary_framework.core.decorator.introspect`)

| Function | Purpose |
|---|---|
| `is_cocoa(cls)` | whether `cls` is marked with `@cocoa` |
| `deps_of(cls)` | the declared dependencies (a tuple) |
| `marked_members(instance, marker)` | `(payload, bound method)` for every marked method, base-first |
| `init_hooks(instance)` / `start_hooks(instance)` / `stop_hooks(instance)` | the hooks of one phase |
| `to_snake(name)` | (`core.infra.naming`) `UserService` → `user_service` |

## Graph algorithms (`canary_framework.runtime.graph`)

| Function | Purpose |
|---|---|
| `build_graph(roots)` | instantiate every root and its transitive dependencies, once each, with no arguments |
| `topological_sort(graph)` | Kahn's algorithm; raises `CircularDependencyError` on a cycle |

## Web extension (`canary_framework.web`)

| Name | Purpose |
|---|---|
| `@web_cocoa(deps=[...], prefix="", tags=(), title="Canary API", version="0.1.0")` | mark a class as both a `@cocoa` and a route holder; `prefix` is **absolute** |
| `@get` / `@post` / `@put` / `@patch` / `@delete` `(path, *, status_code=200, tags=(), summary=None, deprecated=False)` | mark a method as a request handler (must be `async def`) |
| `@route(method, path, ...)` | the generic form of the five above |
| `Header(*, description=None, alias=None)` | a header parameter, written inside `Annotated` |
| `Cookie(*, description=None, alias=None)` | a cookie parameter, written inside `Annotated` |
| `HTTPError(status_code, detail=None, headers=None)` | an error that already is an HTTP concept |
| `WebError` | the root of the extension's errors (inherits `CanaryError`) |
| `RouteRegistrationError` | a route cannot be registered: duplicate method + path, a non-async handler, two body parameters, … |
| `RequestValidationError` | the request cannot satisfy the signature; mapped to 422 |

See [Web Apps](web.md) for usage.
