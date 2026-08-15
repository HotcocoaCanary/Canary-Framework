# Canary Framework

A minimal, decorator-driven framework for **dependency injection**, **lifecycle**, and
**ASGI web apps** — in plain Python.

The framework has two concepts:

- **cocoa** — the smallest unit. A plain class marked with `@cocoa`; its dependencies come
  from `deps=[...]`, its behaviour from `@on_init` / `@on_start` / `@on_stop` hooks.
- **Canary** — the orchestrator. `Canary(*roots)` resolves the dependency graph, sorts it
  topologically, and drives the full lifecycle. It is also an ASGI application.

## Highlights

- **Lazy dependency injection** — no `__init__` plumbing; dependencies are injected as
  `self.<snake_case_name>` at `start()`.
- **Explicit, async-native lifecycle** — `init()` → `start()` → `stop()`; sync or async hooks.
- **Deterministic ordering** — Kahn's topological sort; shared singleton per type, per graph.
- **Multi-root composition** — nest, mix in, or launch any sub-tree independently.
- **Optional web extension** — `@web_cocoa` + `@get`/`@post` turn a unit into a FastAPI-style
  ASGI app with automatic OpenAPI docs.

## Example

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
        await self.pool.connect()  # self.config is injected


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

## Navigation

- [Quick Start](quickstart.md)
- [Cocoa Units](cocoa.md)
- [Runtime (Canary)](canary.md)
- [Lifecycle](lifecycle.md)
- [Dependency Injection](dependency-injection.md)
- [Web Apps](web.md)
- [Architecture](architecture.md)
- [API Reference](api-reference.md)
