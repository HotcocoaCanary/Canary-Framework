# Cocoa Units

A **cocoa** is the framework's minimum unit: a plain Python class marked with `@cocoa`.

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"
```

`@cocoa` does exactly one thing: it writes a marker onto the class. It does **not** rewrite the
class, its methods or its constructor — your class stays a plain class that static type
checkers understand, and it can be subclassed, mixed in and nested cheaply.

## Construction: no arguments, and that is a hard rule

Every instance on the graph is built **by the framework**, with no arguments. So:

```python
@cocoa
class Database:
    def __init__(self, dsn: str) -> None:  # ✗ a required argument; the framework cannot build it
        ...
```

```text
ConstructionError: cannot construct Database: missing a required argument: 'dsn'.
Units are always constructed with no arguments — declare what it needs in
@cocoa(deps=[...]) and read the values from those dependencies in @on_init or @on_start.
```

The way out is to turn the constructor argument into a dependency:

```python
@cocoa
class Config:
    def __init__(self) -> None:
        self.dsn = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_init
    def take_the_dsn(self) -> None:
        self.dsn = self.config.dsn  # the value comes from a collaborator
```

**The rule is not "no constructor", it is "no required parameters".** Setup that needs nothing
from outside still belongs in `__init__`:

```python
@cocoa
class Cache:
    def __init__(self) -> None:
        self._entries: dict[str, object] = {}  # ✓ perfectly fine
        self._hits = 0
```

Parameters with defaults are fine too — the framework passes nothing, so the defaults apply.

## Declaring dependencies

A cocoa declares its dependencies with `deps=[...]`:

```python
@cocoa(deps=[Config])
class Database:
    # self.config is injected at construction
    pass
```

Injection happens at construction: the runtime sets `self.<snake_case name>` for each dependency
(`Config` → `self.config`, `UserService` → `self.user_service`). Because injection is
**assembly**, not startup, `@on_init` already sees its collaborators.

The full contract is in [Dependency Injection](dependency-injection.md).

## Lifecycle hooks

A cocoa may declare any number of hooks per phase. All of them are optional; a unit with
dependencies and no hooks is complete.

| Phase | Decorator | When | What you have |
|---|---|---|---|
| Init | `@on_init` | during `init()`, topological order | dependencies are in place, nothing is running yet |
| Start | `@on_start` | during `start()`, topological order | dependencies in place; acquire resources here |
| Stop | `@on_stop` | during `stop()`, reverse order | reclaim what `@on_start` acquired |

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        # preparation that only needs dependencies, no external resources
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        # connections, background tasks, anything doing IO
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

**How to choose between `@on_init` and `@on_start`**: preparation that touches no external
resource (validation, building indexes, computing derived values, reading configuration) goes in
`@on_init`; anything that opens a connection, a file or a background task goes in `@on_start` —
because only what `@on_start` acquired is ever reclaimed by `@on_stop`.

Each hook may be a plain function or a coroutine function — the runtime checks the return value
and only awaits when it needs to.

Hooks **stack rather than override**: if a mixin declares an `@on_start` and the class declares
another, both run — the mixin's first, then the class's, in definition order.

## Orchestrating with `Canary`

A cocoa is inert until it is handed to a [`Canary`](canary.md), which resolves its dependency
graph and drives the lifecycle:

```python
from canary_framework import Canary


app = Canary(UserService)
await app.init()
await app.start()
assert app[Database].config is app[Config]
await app.stop()
```

## A known boundary

Units are indexed **by type**: one type has exactly one instance per graph. So "two `Database`
instances pointing at different servers" cannot be expressed — write two classes if you need two
instances. That is the hard edge of choosing "type is identity"; lifecycle hooks do not help here.

Also, injected attributes only appear at runtime, so a static type checker does not see
`self.config`. There is currently no way to have both "plain classes" and a happy mypy — this is
the one question the design has not answered.
