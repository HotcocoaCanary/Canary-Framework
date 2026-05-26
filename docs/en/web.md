# Web Package

The `canary_framework.web` package extends Core with HTTP server capabilities. It is a **plugin** — core does not depend on web, and web is optional (`pip install canary-framework[web]`).

## Architecture

```
canary_framework
├── core/                    # Service, Module, DI, Lifecycle, Trace
│   └── (framework-agnostic)
└── web/
    └── fastapi/
        ├── conductor/
        │   └── web_canary.py   # WebCanary(Canary) — overrides start()
        └── decorators/
            └── router.py       # @router, @get, @post, ...
```

**Key principle: everything is a service.** `@router` inherits from `@service` — a router is a service that happens to expose HTTP endpoints. It receives DI, config, and lifecycle hooks just like any other service.

## WebCanary

`WebCanary` extends `Canary` with a single override: `start()` launches a FastAPI + Uvicorn server instead of only calling `on_start` hooks.

```python
from canary_framework.web.fastapi import WebCanary

app = WebCanary(MyRootModule)
await app.init()    # same as Canary: collect, validate, sort, DI, config, on_init
await app.start()   # overridden: boots FastAPI + Uvicorn, registers routes
```

## Router as Service

A `@router`-decorated class is a `@service` with extra metadata (`prefix` and `tags`):

```python
@router(prefix="/api/users", deps=[UserService], tags=["users"])
class UserRouter:
    user_service: UserService  # DI injected

    @get("/{id}")
    async def get(self, id: int) -> User:
        return await self.user_service.get_by_id(id)
```

Because `@router` is a service, it supports:
- **`deps`** — DI injection of dependencies
- **`config`** — pydantic-settings configuration
- **`@on_init` / `@on_start` / `@on_end`** — full lifecycle

Routers are auto-discovered by `WebCanary` — no `@web` decorator needed. Simply include the router class in a module's `services` list (or in the `deps` of a service), and `WebCanary.start()` will register all HTTP routes.

## Further Reading

- [FastAPI Integration](./fastapi.md) — detailed usage, HTTP methods, config prefixes
