# Canary Framework

A minimal, decorator-driven runtime for **dependency injection** and **lifecycle** — pure
Python, zero dependencies.

It is **not a web framework**. It is a runtime container: it assembles a set of objects
according to their dependencies, starts them in order and reclaims them in reverse. What shell
eventually drives those objects — HTTP, a CLI, a scheduler, a message consumer — is that shell's
business: FastAPI, Starlette, Typer, or your own `main()`.

There are only two concepts:

- **cocoa** — the minimum unit. A plain class marked with `@cocoa`; dependencies are declared
  with `deps=[...]`, behaviour with the `@on_init` / `@on_start` / `@on_stop` hooks.
- **Canary** — the orchestrator. `Canary(*roots)` resolves the dependency graph, sorts it
  topologically and drives the whole lifecycle.

## One rule that runs through everything

> **The framework only builds empty shells. Anything that needs input from outside happens in
> the lifecycle.**

Every unit is constructed by the framework **with no arguments** — so `__init__` cannot have
required parameters. Whatever a unit needs, it declares as a dependency and reads in `@on_init`
or `@on_start`. This is not a restriction: a constructor has no counterpart (`@on_start` pairs
with `@on_stop`; "construction" has no "destruction"), so moving work that needs input into the
lifecycle puts every one of those steps into a phase that keeps a ledger and unwinds in reverse.

## Highlights

- **Declarative dependency injection** — no `__init__` wiring; dependencies are injected during
  `init()` as `self.<snake_case name>`, so `@on_init` already sees its collaborators.
- **Explicit, async-native lifecycle** — `init()` → `start()` → `stop()`; hooks may be sync or
  async. Plugging it into any host takes one line: `async with canary:`.
- **Failure paths are part of the design** — a failing `start()` unwinds everything it started;
  `stop()` is the single reclamation path for both normal and failed termination, and it is
  idempotent.
- **Deterministic ordering** — Kahn's topological sort; one shared singleton per type per graph.
- **Multi-root composition** — nest, mix in, or start any subgraph on its own.
- **Zero dependencies** — `pip install canary-framework` pulls in nothing but the standard
  library. A test guards this: after a full lifecycle, nothing from site-packages may appear in
  `sys.modules`.
- **Fast assembly** — building, injecting and running `@on_init` over 1000 units takes ~2.4 ms;
  the framework's own import costs 0.0 ms.

## Example

```python
import asyncio

from canary_framework import Canary, cocoa, on_init, on_start


@cocoa
class Config:
    def __init__(self) -> None:  # no required parameters
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        self.pool = ConnectionPool(self.config.database_url)  # self.config is injected

    @on_start
    async def connect(self) -> None:
        await self.pool.connect()


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

## Navigation

- [Quick Start](quickstart.md)
- [Cocoa Units](cocoa.md)
- [Runtime (Canary)](canary.md)
- [Lifecycle](lifecycle.md)
- [Dependency Injection](dependency-injection.md)
- [Architecture](architecture.md)
- [API Reference](api-reference.md)
