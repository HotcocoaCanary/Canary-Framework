# Quick Start

Install the framework:

```bash
pip install canary-framework
```

Requires Python 3.12+.

## Declare Canaries

Mark any plain class with `@canary`:

```python
from canary_framework import canary


@canary
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"
```

Dependencies are declared through the `__init__` signature:

```python
from canary_framework import canary


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
```

## Add lifecycle behaviour

Use `@start` and `@stop` — both optional, and each may be sync or async:

```python
from canary_framework import canary, start, stop


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.pool = ConnectionPool(self.config.database_url)

    @start
    async def connect(self) -> None:
        await self.pool.connect()

    @stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

## Run with a Flock

`Canary.run()` returns a `Flock` that discovers the graph from the root Canary, topologically sorts it, and drives the lifecycle:

```python
import asyncio

from canary_framework import canary


@canary
class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database


async def main() -> None:
    flock = UserService.run()
    await flock.start()

    try:
        users = flock[UserService]
        assert users.database is flock[Database]
    finally:
        await flock.stop()


asyncio.run(main())
```

Or use it as an async context manager:

```python
async def main() -> None:
    async with UserService.run() as flock:
        assert flock[Database] is flock[UserService].database


asyncio.run(main())
```

## Run a single Canary standalone

A Canary follows Python's async context-manager protocol, so you can drive it directly:

```python
async def main() -> None:
    database = Database(Config())
    async with database:
        ...  # running


asyncio.run(main())
```

## What's next

- [Canary](canary.md) — declaration and the dependency contract.
- [Lifecycle](lifecycle.md) — the state machine and hook ordering.
- [Dependency Injection](dependency-injection.md) — forward references, cycles, scoping.
- [Flock](flock.md) — orchestration, rollback, and shutdown.
