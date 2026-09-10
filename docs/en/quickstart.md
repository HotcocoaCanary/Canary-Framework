# Quick Start

Install the framework:

```bash
pip install canary-framework
```

Python 3.12+ is required. The core has zero dependencies — nothing third-party is pulled in.

## Declare units

Mark any plain class with `@cocoa` and declare dependencies with `deps=[...]`:

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:      # no required parameters
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    # self.config is injected at construction
    pass
```

Units are always constructed by the framework **with no arguments**, so whatever value a unit
needs it declares as a dependency and reads from a collaborator in a lifecycle hook — never as a
constructor parameter.

## Add lifecycle behaviour

Use `@on_init`, `@on_start` and `@on_stop` — all optional, sync or async:

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def setup(self) -> None:
        # dependencies are in place, nothing is running yet
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        # connections and background tasks belong here
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

Preparation that touches no external resource goes in `@on_init`; acquiring resources goes in
`@on_start`: only what `@on_start` acquired is reclaimed by `@on_stop`.

## Run it with `Canary`

`Canary(*roots)` resolves the graph from each root, sorts it and drives the lifecycle explicitly:

```python
import asyncio

from canary_framework import Canary, cocoa


@cocoa(deps=[Database])
class UserService: ...


async def main() -> None:
    app = Canary(UserService)
    await app.init()
    await app.start()
    try:
        users = app[UserService]
        assert users.database is app[Database]
    finally:
        await app.stop()      # callable from any settled state; idempotent


asyncio.run(main())
```

Or use the async context manager:

```python
async def main() -> None:
    async with Canary(UserService) as app:
        assert app[Database] is app[UserService].database


asyncio.run(main())
```

## Compose several roots

`Canary` accepts several roots and merges their graphs into one:

```python
app = Canary(UserService, ReportService)
await app.init()
await app.start()
assert app[Database] is app[UserService].database
```

Any subgraph can be started on its own — `Canary(Database)` starts only `Database` and its
dependency `Config`.

## Plug it into a host

Canary does not care who drives it — it only needs someone to wrap it for the duration of the
run. Any host with a startup/shutdown notion works; FastAPI's lifespan, for instance:

```python
from fastapi import Depends, FastAPI

canary = Canary(UserService)
app = FastAPI(lifespan=canary.lifespan)      # init + start on entry, stop on exit


def provide[T](cls: type[T]):
    def dep() -> T:
        return canary[cls]
    return dep


@app.get("/users/{user_id}")
async def read(user_id: int, users: Annotated[UserService, Depends(provide(UserService))]):
    return users.get(user_id)
```

HTTP, WebSocket, static files, middleware and authentication all belong to the host — those
frameworks already do them well, and Canary does not rebuild them. It only guarantees that your
objects are assembled correctly, started in order and reclaimed in reverse.

## See what the framework assembled

Set the log level to `DEBUG` and the end of startup prints an assembly summary — start order,
dependencies, routes:

```bash
CANARY_LOG_LEVEL=DEBUG python -m examples.library.main
```

## Next

- [Cocoa Units](cocoa.md) — declaration, construction rules, hooks.
- [Runtime (Canary)](canary.md) — composition, multi-root, plugging into a host.
- [Lifecycle](lifecycle.md) — five moments, the state machine, failure paths.
- [Dependency Injection](dependency-injection.md) — injection, sharing, cycles, name clashes.
- [Architecture](architecture.md) — layers, markers, the two phases.
