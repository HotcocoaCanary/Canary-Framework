# Cocoa Units

A **cocoa** is the smallest unit of the framework: an ordinary Python class marked with
`@cocoa`.

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"
```

`@cocoa` does exactly one thing: it stamps the class with a marker. It does **not** change the
class, its methods, or its constructor — your class remains a plain class that static type
checkers understand, and it can be inherited, mixed in, or nested cheaply.

## Declaring dependencies

A cocoa declares its dependencies through `deps=[...]`:

```python
@cocoa(deps=[Config])
class Database:
    # `self.config` is injected at start() time
    pass
```

Dependencies are **injected lazily** — not through `__init__`. At `start()`, the runtime sets
`self.<snake_case_name>` for each dependency (`Config` → `self.config`,
`UserService` → `self.user_service`). This keeps constructors empty and units cheap to build.

```python
@cocoa(deps=[Database, Cache])
class UserService:
    def __init__(self) -> None:
        # No dependency plumbing here.
        self._ready = False
```

See [Dependency Injection](dependency-injection.md) for the full contract.

## Lifecycle hooks

A cocoa may declare any number of hooks per stage. All are optional; a dependency-only unit
with no hooks is complete.

| Stage | Decorator | Runs |
|---|---|---|
| Init | `@on_init` | on `init()`, topological order |
| Start | `@on_start` | on `start()`, topological order, deps already injected |
| Stop | `@on_stop` | on `stop()`, reverse topological order |

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

Each hook may be a plain function or a coroutine function — the runtime detects the result and
`await`s it only when needed.

Hooks are **stacked, not overwritten**: if a mixin declares an `@on_start` hook and the class
declares another, both run — the mixin's first, then the class's, in definition order.

## Orchestrating with `Canary`

A cocoa is inert until handed to a [`Canary`](canary.md), which resolves its graph and drives
its lifecycle:

```python
from canary_framework import Canary


app = Canary(UserService)
await app.init()
await app.start()
assert app[Database].config is app[Config]
await app.stop()
```

See [Runtime (Canary)](canary.md) for orchestration details.
