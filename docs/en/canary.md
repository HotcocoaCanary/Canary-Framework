# Canary

A **Canary** is the smallest runnable unit of the framework: an ordinary Python class marked with `@canary`.

```python
from canary_framework import canary


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
```

`@canary`:

1. registers the class,
2. records its metadata,
3. discovers its lifecycle hooks,
4. makes it a subclass of `Canary`, so it gains the async context-manager protocol and the `state` property.

It does **not** dynamically add lifecycle methods to the class. Your methods remain ordinary methods that static type checkers understand.

## Declaring dependencies

A Canary declares its dependencies through its `__init__` type annotations. Any parameter that has a class annotation (or a string forward reference) and no default value is treated as a dependency:

```python
@canary
class UserService:
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache
```

Parameters with a default value are **not** injected:

```python
@canary
class Repository:
    def __init__(self, database: Database, timeout: float = 30.0) -> None:
        self.database = database
        self.timeout = timeout
```

Here only `database` is a dependency; `timeout` keeps its default.

See [Dependency Injection](dependency-injection.md) for the full contract.

## Lifecycle hooks

A Canary may declare at most one hook per stage:

| Stage | Decorator | Runs |
|---|---|---|
| Start | `@start` | on `__aenter__` |
| Stop | `@stop` | on `__aexit__` |

Each hook is optional. A Canary with no hooks is perfectly valid:

```python
@canary
class UserRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
```

## Orchestrating the graph with `run()`

`Canary.run()` is a classmethod that returns a [`Flock`](flock.md) — a graph handle that discovers this Canary's transitive dependencies, topologically sorts them, and drives the whole graph:

```python
@canary
class Config: ...


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config


@canary
class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database


async with UserService.run() as flock:
    assert flock[Database] is flock[UserService].database
```

See [Flock](flock.md) for orchestration, rollback, and shutdown details.

## Using a Canary directly

A Canary follows Python's async context-manager protocol, so it runs standalone without a `Flock`:

```python
database = Database(Config())

async with database:
    ...  # running
```

`__aenter__` runs `@start`; `__aexit__` runs `@stop`.

You can also call the protocol methods explicitly:

```python
await database.__aenter__()
...
await database.__aexit__(None, None, None)
```

## The `state` property

Every Canary exposes a `state` property drawn from `LifecycleState`:

`NEW → INITIALIZED → STARTING → RUNNING → STOPPING → STOPPED`

with `FAILED` on error. See [Lifecycle](lifecycle.md).
