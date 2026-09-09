<h1 align="center">Canary Framework</h1>

<p align="center">
  A minimal, decorator-driven runtime for <strong>dependency injection</strong> and
  <strong>lifecycle</strong> — pure Python, zero dependencies.
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
pip install canary-framework
```

Nothing third-party comes with it — the framework only uses the standard library.

Python 3.12+ is required.

## The model

- A **cocoa** is the minimum runnable unit — a plain Python class marked with `@cocoa`.
  Dependencies are declared with `deps=[...]`; `@on_init` / `@on_start` / `@on_stop` declare
  optional lifecycle behaviour.
- **Canary** is the orchestrator. `Canary(*roots)` resolves the dependency graph, sorts it
  topologically and drives the whole lifecycle.

It is **not a web framework**. It is a runtime container; what shell drives your objects — HTTP,
a CLI, a scheduler — is that shell's business.

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

## Plug it into a host

Canary knows about no shell. There are only two host shapes in Python and both are supported
directly: hosts taking an async context manager use `canary.lifespan` (ASGI, MCP, FastStream),
hosts taking paired callbacks use `init()`/`start()`/`stop()` (Quart, Sanic, arq, Dramatiq).

```python
from fastapi import Depends, FastAPI

canary = Canary(UserService)
app = FastAPI(lifespan=canary.lifespan)       # init + start on entry, stop on exit


def provide[T](cls: type[T]):
    def dep() -> T:
        return canary[cls]
    return dep


@app.get("/users/{user_id}")
async def read(user_id: int, users: Annotated[UserService, Depends(provide(UserService))]):
    return users.get(user_id)
```

HTTP, WebSocket, static files, middleware and authentication all belong to the host — those
frameworks already do them well. Canary only guarantees that your objects are assembled
correctly, started in order and reclaimed in reverse.

## Examples

[`examples/`](examples) contains runnable examples, from a single unit up through dependency
injection, lifecycle hooks, multi-root composition and a layered library web app.

## Documentation

- [Quick Start](docs/en/quickstart.md)
- [Cocoa Units](docs/en/cocoa.md) · [Runtime (Canary)](docs/en/canary.md)
- [Lifecycle](docs/en/lifecycle.md) · [Dependency Injection](docs/en/dependency-injection.md)
- [Architecture](docs/en/architecture.md) · [API Reference](docs/en/api-reference.md)

## License

Apache-2.0.
