# Quick Start

## Install

```bash
pip install canary-framework
```

Requires Python 3.12 or newer.

## Your first unit

A unit is a plain class that subclasses `Canary`. It is constructed with no arguments, and its
behaviour lives in phase hooks.

```python
from canary_framework import Canary, init


class Config(Canary):
    @init
    def load(self) -> None:
        self.dsn = "postgresql://localhost/dev"
```

A method marked `@init` runs during the `init` phase. Hooks may be synchronous or
`async def`; the framework decides whether to await by looking at the return value.

## Declare dependencies

Use `dep()`. You choose the attribute name:

```python
from canary_framework import Canary, dep, start, stop


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn)

    @stop
    async def close(self) -> None:
        await self.pool.close()
```

`self.config` has type `Config` — type checkers and IDEs see it.

## Run it

```python
import asyncio


class UserService(Canary):
    database = dep(Database)


async def main() -> None:
    async with UserService() as service:
        rows = await service.database.pool.fetch("select 1")
        print(rows)


asyncio.run(main())
```

Entering `async with` advances `init` then `start`; leaving reclaims. The whole graph
(`Config` → `Database` → `UserService`) comes up in dependency order on its own.

## The four actions

For step-by-step control, use the explicit form — it behaves exactly like `async with`:

```python
service = UserService()
await service.init()     # every @init
await service.start()    # every @start
await service.stop()     # every @stop, in reverse
```

Calling `start()` without `init()` raises `LifecycleError` rather than silently skipping a
phase.

## What belongs in which phase

- **Construction**: nothing. A unit must be constructible with no arguments, and dependencies
  are not available yet.
- **`@init`**: preparation that needs only dependencies and acquires nothing external —
  validation, building indexes, deriving values.
- **`@start`**: acquire resources, start background tasks. Only what is acquired here is
  reclaimed by `@stop`.
- **`@stop`**: release what `@start` acquired.

## A complete example

`examples/library/` in the repository is a five-layer graph:

```
LibraryApp → LibraryService → three repositories → Database → Config
```

Run it:

```bash
python examples/library/main.py
```

## Hosting

The framework knows nothing about shells. ASGI, a CLI or a message consumer all wire up the
same way:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

service = UserService()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with service:
        yield


app = FastAPI(lifespan=lifespan)
```

More hosts, test doubles and retry: see [Patterns](patterns.md).
