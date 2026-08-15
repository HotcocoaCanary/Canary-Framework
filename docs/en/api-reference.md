# API Reference

## `canary`

```python
def canary(cls: type[T]) -> type[T]
```

Declares `cls` as a Canary. Returns a `Canary` subclass carrying the same namespace.

Raises `RegistrationError` if `cls` is already a Canary, uses `__slots__`, declares an invalid constructor, or declares duplicate hooks for one stage.

## `Canary`

Base class shared by every Canary.

### `run` — classmethod

```python
@classmethod
def run(cls) -> Flock
```

Returns a `Flock` that orchestrates this Canary's transitive dependency graph.

### `state` — property

```python
@property
def state(self) -> LifecycleState
```

Returns the current lifecycle state of the instance.

### `__aenter__`

```python
async def __aenter__(self) -> Canary
```

Runs the `@start` hook and enters the `RUNNING` state. Raises `LifecycleError` unless the Canary is `INITIALIZED`.

### `__aexit__`

```python
async def __aexit__(self, exc_type, exc, tb) -> bool | None
```

Runs the `@stop` hook and enters the `STOPPED` state. No-op if not running.

## `start`, `stop`

```python
def start(func: F) -> F
def stop(func: F) -> F
```

Mark a method as the startup / stop hook of a Canary. Each may be sync or async, and at most one of each stage is allowed per Canary.

## `Flock`

```python
class Flock:
    def __init__(self, root: type[Canary]) -> None
```

The lifecycle orchestrator returned by `Canary.run()`. Raises `DependencyError` if `root` is not a registered Canary.

### `root` — property

The root Canary type.

### `state` — property

```python
@property
def state(self) -> FlockState
```

The current orchestration state.

### `order` — property

```python
@property
def order(self) -> tuple[type[Canary], ...]
```

Canary types in dependency-first topological order.

### `instances` — property

```python
@property
def instances(self) -> dict[type[Canary], Canary]
```

A copy of the created instances, keyed by Canary type.

### `__getitem__`

```python
def __getitem__(self, canary_type: type[T]) -> T
```

Returns the shared instance of `canary_type` in this graph. Raises `KeyError` if absent.

### `start`

```python
async def start(self) -> None
```

Builds the graph, constructs, and starts every Canary in topological order. Raises `StartupError` on failure (after rollback).

### `stop`

```python
async def stop(self) -> None
```

Stops running Canaries in reverse topological order. Raises `LifecycleError` if not running.

### `__aenter__` / `__aexit__`

Async context-manager protocol wrapping `start` / `stop`.

## Enums

### `LifecycleState`

Per-Canary state: `NEW`, `INITIALIZED`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `FAILED`.

### `FlockState`

Per-Flock state: `NEW`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `FAILED`.

## Exceptions

| Exception | Base | Meaning |
|---|---|---|
| `CanaryError` | `Exception` | base class for all framework errors |
| `RegistrationError` | `CanaryError` | invalid Canary declaration |
| `DependencyError` | `CanaryError` | dependency resolution or wiring failure |
| `CircularDependencyError` | `DependencyError` | dependency cycle; exposes `.cycle` |
| `LifecycleError` | `CanaryError` | illegal lifecycle operation |
| `StartupError` | `CanaryError` | startup failure; exposes `.canary_type` |
