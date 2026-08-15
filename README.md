<h1 align="center">Canary Framework</h1>

<p align="center">
  A minimal, decorator-driven framework for <strong>dependency injection</strong>,
  <strong>lifecycle</strong>, and <strong>ASGI web apps</strong> — in plain Python.
</p>

<p align="center">
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="PyPI" src="https://img.shields.io/pypi/v/canary-framework.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/canary-framework.svg"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/canary-framework.svg"></a>
</p>

<p align="center">
  <a href="README_ZH.md">中文</a> ·
  <a href="https://hotcocoacanary.github.io/Canary-Framework/">Documentation</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

## Install

```bash
pip install canary-framework            # core
pip install "canary-framework[web]"     # + web extension (ASGI / OpenAPI)
```

Requires Python 3.12+.

## The model

- **cocoa** is the smallest runnable unit — a plain Python class marked with `@cocoa`.
  Dependencies are declared with `deps=[...]`; `@on_init` / `@on_start` / `@on_stop` declare
  optional lifecycle behaviour.
- **Canary** is the orchestrator. `Canary(*roots)` resolves the dependency graph, topologically
  sorts it, and drives the full lifecycle — and is itself an ASGI application.

## Quick start

```python
import asyncio

from canary_framework import Canary, cocoa, on_start


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_start
    async def connect(self) -> None:
        print(f"connecting to {self.config.database_url}")  # self.config is injected


@cocoa(deps=[Database])
class UserService: ...


async def main() -> None:
    app = Canary(UserService)
    await app.init()  # build the graph, run @on_init
    await app.start()  # inject deps, run @on_start
    assert app[Database].config is app[Config]
    await app.stop()  # run @on_stop in reverse order


asyncio.run(main())
```

## Dependency injection

Cocoas declare dependencies with `deps=[...]` — no `__init__` plumbing, no DSL. Each dependency
is injected lazily as `self.<snake_case_name>` at `start()`:

```python
@cocoa(deps=[Database, Cache])
class UserService:
    def __init__(self) -> None:
        self._ready = False  # no dependency wiring here
```

`Canary` resolves the graph from the roots, injects one shared instance per type, and drives
initialization and startup in topological order.

## Lifecycle

Three optional hooks — each sync or async, any number per stage:

| Stage | Decorator | Runs |
|---|---|---|
| Init | `@on_init` | `init()`, topological order |
| Start | `@on_start` | `start()`, topological order, deps injected |
| Stop | `@on_stop` | `stop()`, reverse topological order |

```python
@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None: ...

    @on_start
    async def connect(self) -> None: ...

    @on_stop
    async def disconnect(self) -> None: ...
```

## Web apps

The `web` extension turns a `@cocoa` service into a FastAPI-style ASGI app with automatic
OpenAPI docs:

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService])
class LibraryAPI:
    @get("/books/{book_id}")
    async def get_book(self, book_id: int) -> dict: ...

    @post("/books/{book_id}/borrow")
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict: ...


app = Canary(LibraryAPI)  # `app` is the ASGI application
```

```bash
uvicorn examples.library.web:app --reload
# GET /docs  ·  /redoc  ·  /openapi.json
```

## Examples

Runnable examples live in [`examples/`](examples), from a minimal unit through dependency
injection, lifecycle hooks, multi-root composition, and a layered library web app.

## Documentation

- [Quick Start](docs/en/quickstart.md)
- [Cocoa Units](docs/en/cocoa.md) · [Runtime (Canary)](docs/en/canary.md)
- [Lifecycle](docs/en/lifecycle.md) · [Dependency Injection](docs/en/dependency-injection.md)
- [Web Apps](docs/en/web.md) · [Architecture](docs/en/architecture.md) · [API Reference](docs/en/api-reference.md)

## License

Apache-2.0.
