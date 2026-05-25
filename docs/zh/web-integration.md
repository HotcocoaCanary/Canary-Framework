# Web 集成

通过 `cf[web]` 和 `WebCanary` 接入 FastAPI。

## 最小 Web 写法

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

## 完整 Web 写法：服务 + 路由类

```python
from cf import service, on_init, Context
from cf.web.fastapi import web, router, get, post, WebCanary

# 路由类 —— 接收统一 Context
@router(prefix="/api/users")
class UserRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service               # 所属服务实例
        self.db = ctx.resolve(DBService)     # 沿父链查找依赖

    @get("/")
    async def list_users(self):
        return []

    @post("/")
    async def create_user(self, name: str):
        return {"name": name}

# 服务 —— 绑定路由类
@web(routers=[UserRouter])
@service(name="UserService", deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context):
        pass
```

## 统一 Context

路由类的 `__init__` 和服务的 `on_init` 接收**同一个 Context 类**：

- `ctx.config` — 配置（沿 parent 链向上查找）
- `ctx.service` — 所属服务/模块实例
- `ctx.resolve(SomeService)` — 沿 parent 链在父模块的 sub_services 中查找

```python
@router(prefix="/api")
class Router:
    def __init__(self, ctx: Context):
        self.svc = ctx.service           # 调用业务方法
        self.db = ctx.resolve(DBService) # 手动解析依赖
```

## 装饰器速查

| 装饰器 | 用法 |
|--------|------|
| `@web` | `@web()` 或 `@web(routers=[R1, R2])` |
| `@router` | `@router(prefix="/api/users")` |
| `@get` | `@get("/users/{id}")` |
| `@post` | `@post("/users", status_code=201)` |
| `@put` | `@put("/users/{id}")` |
| `@delete` | `@delete("/users/{id}")` |
| `@patch` | `@patch("/users/{id}")` |
