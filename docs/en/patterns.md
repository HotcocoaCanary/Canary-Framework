# Patterns

Common tasks, written with nothing but `Canary`, `dep()` and phases.

## Test doubles

Subclass the unit you replace, and provide the instance to the scope before the lifecycle
begins. Every `dep(Database)` in the graph then returns the double:

```python
import pytest

from canary_framework import scope_of


class FakeDatabase(Database):
    @start
    async def connect(self) -> None:
        self.rows: list[dict] = []

    @stop
    async def close(self) -> None: ...


@pytest.fixture
async def service():
    service = UserService()
    scope_of(service).provide(Database, FakeDatabase())
    async with service:
        yield service


async def test_register(service: UserService) -> None:
    await service.register("ada")
    assert service.database.rows == [{"name": "ada"}]
```

The double runs its own hooks and enters the dependencies its own class declares. See
[Units › Substitutes](canary.md#substitutes) for the rules.

## Choosing an implementation from configuration

A unit decides for itself what it connects to. Read the configuration from a dependency and
pick the implementation in `@start`:

```python
import os


class Settings(Canary):
    @init
    def load(self) -> None:
        self.backend = os.environ.get("DB_BACKEND", "sqlite")
        self.url = os.environ.get("DB_URL", "app.db")


class Database(Canary):
    settings = dep(Settings)
    driver: Driver | None = None

    @start
    async def connect(self) -> None:
        match self.settings.backend:
            case "postgres":
                self.driver = PostgresDriver(self.settings.url)
            case "sqlite":
                self.driver = SqliteDriver(self.settings.url)
            case other:
                raise ValueError(f"unknown DB_BACKEND: {other}")
        await self.driver.open()

    @stop
    async def close(self) -> None:
        if self.driver is not None:
            await self.driver.close()
```

Everything else depends on `Database` and never learns which backend is behind it.

Construct the backends inside the hook rather than declaring each one with `dep()`:
dependencies are static, so every declared unit is brought up whether it is used or not.

## Hooks that fail halfway

A `@start` that raises halfway runs its unit's `@stop` at once, and `start()` then releases the
dependencies it brought up. Write `@stop` to release only what was actually acquired — above,
`driver` defaults to `None` for exactly this reason.

## Blocking work in hooks

Synchronous hooks run on the event loop. A slow one holds up every unit entering alongside it,
not just its dependents. Move blocking calls to a thread:

```python
class Index(Canary):
    @init
    async def build(self) -> None:
        self.index = await asyncio.to_thread(build_index, self.corpus.path)
```

Quick synchronous hooks — reading a setting, building a small object — are fine as they are.

## Bounding shutdown

`stop()` waits for every `@stop` — dependents first, independent units concurrently — and for
any `start()` still in flight. To give shutdown a deadline, wrap it in `asyncio.timeout`:

```python
try:
    async with asyncio.timeout(10):
        await service.stop()
except TimeoutError:
    log.warning("shutdown timed out")
```

Hooks running when the deadline hits are cancelled and not retried. Units not reached yet keep
what they acquired, so calling `stop()` again carries on from there.

## Hosting

The framework knows nothing about shells. Hosts that take an async context manager:

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

Hosts that take start and stop callbacks get the unit's methods:

```python
scheduler.on_startup(service.init, service.start)
scheduler.on_shutdown(service.stop)
```

Scripts and CLIs:

```python
async def main() -> None:
    async with UserService() as service:
        await service.run_once()


asyncio.run(main())
```

## Restart and retry

`stop()` undoes `start`, so a stopped graph can start again. A failed `start()` has already
released what it brought up, so retrying is just calling it again:

```python
for attempt in range(3):
    try:
        await service.start()
        break
    except ConnectionError:
        if attempt == 2:
            raise
        await asyncio.sleep(2**attempt)
```

`@init` runs once per scope. See [Lifecycle › Starting again](lifecycle.md#starting-again).
