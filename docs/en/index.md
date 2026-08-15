# Canary Framework

A typed, decorator-driven async framework for lifecycle and dependency injection.

The framework has two core concepts:

- **Canary** — the smallest runnable unit. A plain Python class marked with `@canary`; its dependencies come from `__init__` type annotations.
- **Flock** — the orchestrator returned by `Canary.run()` that drives a Canary's full transitive dependency graph.

## Highlights

- Dependency injection through native constructor type annotations — no DSL.
- Lifecycle hooks `@start`, `@stop` mapped onto Python's native `__aenter__` / `__aexit__` protocol.
- Automatic dependency-graph construction and topological sorting.
- Startup rollback and deterministic reverse-order shutdown.
- A Canary runs standalone (`async with ...`) or under a `Flock` (`Canary.run()`).

## Example

```python
import asyncio

from canary_framework import canary, start, stop


@canary
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config

    @start
    async def connect(self) -> None: ...

    @stop
    async def disconnect(self) -> None: ...


@canary
class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database


async def main() -> None:
    async with UserService.run() as flock:
        assert flock[Database] is flock[UserService].database


asyncio.run(main())
```

## Navigation

- [Quick Start](quickstart.md)
- [Canary](canary.md)
- [Lifecycle](lifecycle.md)
- [Dependency Injection](dependency-injection.md)
- [Flock](flock.md)
- [Architecture](architecture.md)
- [API Reference](api-reference.md)
