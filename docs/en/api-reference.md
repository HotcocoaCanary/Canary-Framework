# API Reference

Everything below is exported from `canary_framework` unless stated otherwise.

## `cocoa`

```python
def cocoa(cls=None, *, deps: list[type] | None = None)
```

Marks `cls` as a cocoa — the minimum unit. `deps` is the ordered list of dependency types.
Usable directly or as a decorator factory:

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...
```

## `on_init` / `on_start` / `on_stop`

```python
def on_init(fn) -> fn
def on_start(fn) -> fn
def on_stop(fn) -> fn
```

Register a method as a lifecycle hook. Each accepts sync or async functions, and any number of
hooks may share a stage.

## `Canary`

```python
class Canary(*roots: type)
```

The orchestrator. Raises `TypeError` if a root is not decorated with `@cocoa`.

### `state` — property

```python
@property
def state(self) -> LifecycleState
```

The current lifecycle state.

### `order` — property

```python
@property
def order(self) -> tuple[type, ...]
```

Unit types in topological startup order (dependencies first).

### `instances` — property

```python
@property
def instances(self) -> tuple[object, ...]
```

The instances, in topological order.

### `__getitem__`

```python
def __getitem__(self, cls: type[T]) -> T
```

Returns the shared singleton for `cls` in this graph. Raises `KeyError` if absent.

### `init`

```python
async def init(self) -> None
```

Builds the graph, topologically sorts it, and runs `@on_init` in order.
`NEW → INITIALIZED`.

### `start`

```python
async def start(self) -> None
```

Injects dependencies, runs `@on_start` in order, then collects any serving app.
`INITIALIZED → STARTED`.

### `stop`

```python
async def stop(self) -> None
```

Runs `@on_stop` in reverse topological order. `STARTED → STOPPED`.

### `__call__` — ASGI

```python
async def __call__(self, scope, receive, send) -> None
```

Serves ASGI: `lifespan` drives the lifecycle; other scopes are delegated to the serving app a
unit exposed during `start()`.

### `__aenter__` / `__aexit__`

Async context-manager protocol wrapping `init()` + `start()` / `stop()`.

## Enums

### `LifecycleState`

`NEW`, `INITIALIZING`, `INITIALIZED`, `STARTING`, `STARTED`, `STOPPING`, `STOPPED`, `FAILED`.

### `State`

The base enum every state enum inherits; a mount point for `issubclass` checks, not itself used.

## Exceptions

| Exception | Base | Meaning |
|---|---|---|
| `CanaryError` | `Exception` | base class for every framework error |
| `CircularDependencyError` | `CanaryError` | dependency cycle; exposes `.cycle` (list of type names) |
| `LifecycleError` | `CanaryError` | illegal lifecycle transition |

All framework and extension errors inherit `CanaryError`, so `except CanaryError` catches
everything.

## Introspection (`canary_framework.core`)

| Function | Purpose |
|---|---|
| `is_cocoa(cls)` | `True` if `cls` was decorated with `@cocoa` |
| `deps_of(cls)` | the declared dependencies |
| `hooks_of(instance, marker)` | marked methods of `instance`, base-first |
| `init_hooks(instance)` / `start_hooks(instance)` / `stop_hooks(instance)` | hooks for a stage |
| `to_snake(name)` | `UserService` → `user_service` |

## Graph algorithms (`canary_framework.runtime`)

| Function | Purpose |
|---|---|
| `build_graph(roots)` | instantiate each root and its transitive deps, one instance each |
| `topological_sort(graph)` | Kahn's algorithm; raises `CircularDependencyError` on a cycle |

## Web extension (`canary_framework.web`)

| Name | Purpose |
|---|---|
| `@web_cocoa(deps=[...], prefix=..., title=..., version=...)` | mark a class as a `@cocoa` *and* an HTTP route holder; `prefix` nests along `deps` |
| `@get` / `@post` / `@put` / `@patch` / `@delete` / `@route(method, path)` | mark a method as a route handler |
| `Query` / `Path` / `Header` / `Cookie` / `Body` | parameter source markers (as a default or via `Annotated`) |
| `WebError` | base class for web-extension errors |
| `RouteRegistrationError` | duplicate method + path |
| `MissingParameterError` | required request parameter absent (maps to HTTP 422) |

See [Web Apps](web.md) for usage.
