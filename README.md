<h1 align="center">Canary Framework 0.7</h1>

<p align="center">A typed, decorator-driven async framework for lifecycle and dependency injection.</p>

[中文](README_ZH.md) · [Documentation](docs/en/index.md) · [Changelog](CHANGELOG.md)

## Install

```bash
pip install canary-framework
```

Requires Python 3.12+.

## The model

- **Canary** is the smallest runnable unit — a plain Python class marked with `@canary`. Dependencies are declared through `__init__` type annotations; `@start` and `@stop` declare optional lifecycle behaviour.
- **Flock** is the orchestrator returned by `Canary.run()`. It receives a root Canary, discovers its transitive dependencies, topologically sorts them, and drives their full lifecycle in dependency order.

## Quick start

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

## Dependency injection

Canaries declare dependencies with constructor type annotations — no DSL:

```python
@canary
class UserService:
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache
```

`Canary.run()` resolves the graph from the root, injects a single shared instance per Canary type, and drives initialization and startup in topological order.

## Lifecycle

`@start` and `@stop` map onto Python's native async context-manager protocol (`__aenter__` / `__aexit__`), so a Canary runs both under a `Flock` and standalone:

```python
database = Database(config)
async with database:
    ...  # running
```

## Examples

Runnable examples are in [`examples/`](examples), from a minimal Canary through dependency injection, lifecycle hooks, standalone usage, and a layered application.

## Breaking release

0.7.0 removes the Service / Router / Module web layer entirely. See [What's New](docs/en/whats-new.md) for migration notes.

## License

Apache-2.0.
