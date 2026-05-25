# Web Integration

Use `cf[web]` and `WebCanary` for FastAPI integration.

## Minimal Web

```python
import asyncio
from cf import module
from cf.web.fastapi import web, get, WebCanary

@web()
@module(name="App", services=[])
class App:
    @get("/")
    def index(self):
        return "ok"

async def main():
    app = WebCanary(App)
    await app.init()
    await app.start()

asyncio.run(main())
```

## Full Web: Service + Router Class

```python
from cf import service, on_init, Context
from cf.web.fastapi import web, router, get, post, WebCanary

@router(prefix="/api/users")
class UserRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service               # owning service instance
        self.db = ctx.resolve(DBService)     # resolve dependency via parent chain

    @get("/")
    async def list_users(self):
        return []

    @post("/")
    async def create_user(self, name: str):
        return {"name": name}

@web(routers=[UserRouter])
@service(name="UserService", deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context):
        pass
```

## Unified Context

Router `__init__` and service `on_init` receive the **same Context class**:

- `ctx.config` — config (looked up via parent chain)
- `ctx.service` — owning service/module instance
- `ctx.resolve(SomeService)` — look up a registered service via parent chain

```python
@router(prefix="/api")
class Router:
    def __init__(self, ctx: Context):
        self.svc = ctx.service           # call business methods
        self.db = ctx.resolve(DBService) # manual dependency resolution
```

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
