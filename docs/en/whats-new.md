# What's New in 0.7.0

0.7.0 is a destructive refactor. The Service / Router / Module web layer is gone, replaced by a pure **Canary / Flock** lifecycle and dependency-injection engine.

## Migration table

| 0.6.0 | 0.7.0 |
|---|---|
| `@service()` / `ServiceBase` | `@canary` |
| `@router()` / `RouterBase` | removed |
| `@module()` / `ModuleBase` | removed |
| `@get` / `@post` / … | removed |
| `on_init` / `on_startup` / `on_shutdown` | `@start` / `@stop` |
| `await app.init()` + ASGI lifespan | `Canary.run()` + `await flock.start()` |
| config service | `@canary class Config` |
| OpenAPI / docs endpoints | removed |

## Before

```python
from canary_framework import get, router
from canary_framework.core import RouterBase


@router(prefix="/hello", tags=("Hello",))
class HelloRouter(RouterBase):
    @get("")
    async def hello(self) -> dict[str, str]:
        return {"message": "Hello, Canary!"}
```

## After

```python
from canary_framework import canary


@canary
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config


async def main() -> None:
    async with Database.run() as flock:
        assert flock[Database].config is flock[Config]


asyncio.run(main())
```

## Key changes

- **Canaries replace Services.** A Canary is a plain class; dependencies come from `__init__` annotations.
- **Lifecycle hooks replace lifecycle methods.** `@start`, `@stop` map onto `__aenter__` / `__aexit__`.
- **`Flock` replaces the runtime root.** `Canary.run()` returns a `Flock` that discovers, sorts, and drives the dependency graph.
- **No web layer.** Routing, OpenAPI, and configuration were removed; the framework is a pure engine.
- **Standalone usage.** A Canary is directly an async context manager.
