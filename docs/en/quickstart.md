# Quick Start

Install the framework:

```bash
pip install canary-framework
```

Requires Python 3.12+.

## Declare units

Mark any plain class with `@cocoa`. Dependencies are declared with `deps=[...]`:

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    # `self.config` is injected at start() time
    def __init__(self) -> None:
        self.pool = None
```

## Add lifecycle behaviour

Use `@on_init`, `@on_start` and `@on_stop` — all optional, each sync or async:

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def setup(self) -> None:
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

## Run with `Canary`

`Canary(*roots)` resolves the graph from each root, topologically sorts it, and drives the
lifecycle explicitly:

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
        await app.stop()


asyncio.run(main())
```

Or use it as an async context manager:

```python
async def main() -> None:
    async with Canary(UserService) as app:
        assert app[Database] is app[UserService].database


asyncio.run(main())
```

## Compose multiple roots

`Canary` accepts several roots, composing their graphs into one:

```python
app = Canary(UserService, ReportService)
await app.start()
assert app[Database] is app[UserService].database
```

Any sub-tree can be launched on its own — `Canary(Database)` starts only `Database` and its
dependencies (`Config`).

## Expose it as a web app

Add the optional `web` extension to serve a unit over HTTP:

```bash
pip install "canary-framework[web]"
```

```python
from canary_framework import Canary
from canary_framework.web import get, web_cocoa


@web_cocoa(deps=[Database])
class LibraryAPI:
    @get("/books")
    async def list_books(self) -> list[dict]:
        return self.database.all("books")


app = Canary(LibraryAPI)  # `app` is the ASGI application
```

```bash
uvicorn examples.library.web:app --reload
```

Open `/docs` for the interactive OpenAPI document. See [Web Apps](web.md).

## What's next

- [Cocoa Units](cocoa.md) — declaration, dependencies and hooks.
- [Runtime (Canary)](canary.md) — orchestration, multi-root and ASGI.
- [Lifecycle](lifecycle.md) — the state machine and hook ordering.
- [Dependency Injection](dependency-injection.md) — injection, sharing, cycles.
