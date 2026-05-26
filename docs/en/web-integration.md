# Web Integration

Use `canary-framework[web]` and `WebCanary` for FastAPI integration.

## Minimal Web

```python
import asyncio
from canary_framework import module
from canary_framework.web.fastapi import web, get, WebCanary

@web()
@module(name="App", services=[])
class App:
    @get("/")
    def index(self) -> dict:
        return {"status": "ok"}

async def main() -> None:
    app = WebCanary(App)
    await app.init()
    await app.start()

asyncio.run(main())
```

## Full Web: Service + Router Class

```python
from canary_framework import service, on_init, Context
from canary_framework.web.fastapi import web, router, get, post, WebCanary

# Router class — receives unified Context
@router(prefix="/api/users")
class UserRouter:
    def __init__(self, ctx: Context) -> None:
        self.db = ctx.resolve(DBService)     # resolve dependency via parent chain

    @get("/")
    async def list_users(self) -> list[dict]:
        return await self.db.list_users()

    @post("/")
    async def create_user(self, name: str) -> dict:
        return {"name": name}

# Service — binds router classes
@web(routers=[UserRouter])
@service(name="UserService", deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context) -> None:
        pass
```

## Unified Context

Router `__init__` and service `on_init` receive the **same Context class**:

- `ctx.get_config(ConfigType)` — type-safe config access
- `ctx.get_service(ServiceType)` — type-safe service/module instance access
- `ctx.resolve(ServiceClass)` — look up a registered service via parent chain

```python
@router(prefix="/api")
class Router:
    def __init__(self, ctx: Context) -> None:
        self.db = ctx.resolve(DBService)        # manual dependency resolution
        self.svc = ctx.get_service(MyService)    # type-safe access
```

## Config Prefixes

WebCanary distributes params from root module `@config` by prefix:

| Prefix | Consumer | Example |
|--------|----------|---------|
| `uvicorn_*` | uvicorn.Config | `uvicorn_host` → `host` |
| `fastapi_*` | FastAPI() | `fastapi_title` → `title` |
| (no prefix) | business config | `db_url` |

## Decorator Quick Reference

| Decorator | Usage |
|-----------|-------|
| `@web` | `@web()` or `@web(routers=[R1, R2])` |
| `@router` | `@router(prefix="/api/users")` |
| `@get` | `@get("/users/{id}")` |
| `@post` | `@post("/users", status_code=201)` |
| `@put` | `@put("/users/{id}")` |
| `@delete` | `@delete("/users/{id}")` |
| `@patch` | `@patch("/users/{id}")` |

## Error Handling

If FastAPI/Uvicorn extensions are not installed, `WebCanary.start()` raises a clear `ImportError`:

```python
# Install: pip install canary-framework[web]
```

Default binding is `127.0.0.1` (secure default). Override via `uvicorn_host` config.
