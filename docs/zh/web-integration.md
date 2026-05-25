# Web 集成

通过 `canary-framework[web]` 和 `WebCanary` 接入 FastAPI。

## 最小 Web 写法

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

## 完整 Web 写法：服务 + 路由类

```python
from canary_framework import service, on_init, Context
from canary_framework.web.fastapi import web, router, get, post, WebCanary

# 路由类 —— 接收统一 Context
@router(prefix="/api/users")
class UserRouter:
    def __init__(self, ctx: Context) -> None:
        self.db = ctx.resolve(DBService)     # 沿父链查找依赖

    @get("/")
    async def list_users(self) -> list[dict]:
        return await self.db.list_users()

    @post("/")
    async def create_user(self, name: str) -> dict:
        return {"name": name}

# 服务 —— 绑定路由类
@web(routers=[UserRouter])
@service(name="UserService", deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context) -> None:
        pass
```

## 统一 Context

路由类的 `__init__` 和服务的 `on_init` 接收**同一个 Context 类**：

- `ctx.config_as(ConfigType)` — 类型安全的配置访问
- `ctx.service_as(ServiceType)` — 类型安全的服务/模块实例访问
- `ctx.resolve(ServiceClass)` — 沿 parent 链查找已注册的服务

```python
@router(prefix="/api")
class Router:
    def __init__(self, ctx: Context) -> None:
        self.db = ctx.resolve(DBService)        # 手动解析依赖
        self.svc = ctx.service_as(MyService)    # 类型安全访问
```

## 配置前缀

WebCanary 按前缀从根模块 `@config` 分发参数：

| 前缀 | 消费者 | 示例 |
|------|--------|------|
| `uvicorn_*` | uvicorn.Config | `uvicorn_host` → `host` |
| `fastapi_*` | FastAPI() | `fastapi_title` → `title` |
| (无前缀) | 业务配置 | `db_url` |

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

## 异常处理

如果未安装 FastAPI/Uvicorn 扩展，`WebCanary.start()` 会抛出清晰的 `ImportError`：

```python
# 安装: pip install canary-framework[web]
```

默认绑定 `127.0.0.1`（安全默认值），可通过 `uvicorn_host` 配置修改。
