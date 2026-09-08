<h1 align="center">Canary Framework</h1>

<p align="center">
  A minimal, decorator-driven framework for <strong>dependency injection</strong>,
  <strong>lifecycle</strong> and <strong>ASGI web apps</strong> — pure Python.
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
pip install canary-framework            # core (zero third-party dependencies)
pip install "canary-framework[web]"     # + web extension (ASGI / OpenAPI)
```

Python 3.12+ is required.

## The model

- A **cocoa** is the minimum runnable unit — a plain Python class marked with `@cocoa`.
  Dependencies are declared with `deps=[...]`; `@on_init` / `@on_start` / `@on_stop` declare
  optional lifecycle behaviour.
- **Canary** is the orchestrator. `Canary(*roots)` resolves the dependency graph, sorts it
  topologically and drives the whole lifecycle — and it is an ASGI app itself.

One rule runs through everything:

> **The framework only builds empty shells. Anything that needs input from outside happens in the
> lifecycle.**

Units are always constructed by the framework **with no arguments**, so `__init__` may not have
required parameters — whatever a unit needs, it declares as a dependency and reads from a
collaborator in a lifecycle hook. That way every step needing input lands in a phase that keeps a
ledger and unwinds in reverse.

## Quick start

```python
import asyncio

from canary_framework import Canary, cocoa, on_init, on_start


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        print(f"about to connect to {self.config.database_url}")  # self.config is injected

    @on_start
    async def connect(self) -> None: ...


@cocoa(deps=[Database])
class UserService: ...


async def main() -> None:
    app = Canary(UserService)
    await app.init()   # build, sort, inject, run @on_init
    await app.start()  # run @on_start
    assert app[Database].config is app[Config]
    await app.stop()   # run @on_stop in reverse


asyncio.run(main())
```

## Dependency injection

A cocoa declares its dependencies with `deps=[...]` — no `__init__` wiring, no extra DSL. Each
dependency is injected during `init()` as `self.<snake_case name>`, so `@on_init` already sees
its collaborators:

```python
@cocoa(deps=[Database, Cache])
class UserService:
    @on_init
    def check(self) -> None:
        assert self.database is not None
```

Two dependencies whose snake_case names collide raise `InjectionError` instead of letting the
last one win.

## Lifecycle

Three optional hooks, each sync or async, any number per phase:

| Phase | Decorator | What you have |
|---|---|---|
| Init | `@on_init` | dependencies in place, nothing running yet |
| Start | `@on_start` | acquire resources, start background tasks |
| Stop | `@on_stop` | reclaim, in reverse |

Failure paths are part of the design: a failing `start()` unwinds everything it started, and
`stop()` is the **single** reclamation path for both normal and failed termination, callable
repeatedly — `finally: await app.stop()` is always safe.

## Web apps

The `web` extension turns `@cocoa` services into an ASGI app with a generated OpenAPI document:

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService], prefix="/api", tags=["library"])
class LibraryAPI:
    @get("/books/{book_id}")
    async def get_book(self, book_id: int) -> dict: ...

    @post("/books/{book_id}/borrow", status_code=201)
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict: ...


app = Canary(LibraryAPI)  # `app` is the ASGI app
```

```bash
uvicorn examples.library.web:app --reload
# GET /docs  ·  /openapi.json
```

Parameter sources follow a single inference rule: **scalars come from the query string (or the
path when the name matches a placeholder); everything else comes from the body.** Headers and
cookies cannot be inferred, so declare them with `Annotated[str, Header()]`. Handlers must be
`async def` — a synchronous one stalls the whole process, and the framework refuses it at
assembly time.

Signatures are compiled **at assembly time** into a value-fetching plan, so the request path does
no reflection at all.

## Examples

[`examples/`](examples) contains runnable examples, from a single unit up through dependency
injection, lifecycle hooks, multi-root composition and a layered library web app.

## Documentation

- [Quick Start](docs/en/quickstart.md)
- [Cocoa Units](docs/en/cocoa.md) · [Runtime (Canary)](docs/en/canary.md)
- [Lifecycle](docs/en/lifecycle.md) · [Dependency Injection](docs/en/dependency-injection.md)
- [Web Apps](docs/en/web.md) · [Architecture](docs/en/architecture.md) · [API Reference](docs/en/api-reference.md)

## License

Apache-2.0.
