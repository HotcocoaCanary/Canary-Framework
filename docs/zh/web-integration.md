# Web 集成

通过 `canary-framework[web]` 和 `WebCanary` 接入 FastAPI。

## 最小 Web 写法

```python
import asyncio
from canary_framework import module
from canary_framework.web.fastapi import get, WebCanary

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
from canary_framework.web.fastapi import router, get, post, WebCanary

@router(prefix="/api/users", deps=[DBService])
class UserRouter:
    db_service: DBService

    @get("/")
    async def list_users(self) -> list[dict]:
        return await self.db_service.list_users()

    @post("/")
    async def create_user(self, name: str) -> dict:
        return {"name": name}

@service(name="UserService", deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context) -> None:
        pass
```

## 统一 Context

路由类可通过 `deps=[Svc]` 声明依赖注入，或通过 `@on_init` 接收 Context：

- `ctx.get_config(ConfigType)` — 类型安全的配置访问
- `ctx.get_service(ServiceType)` — 类型安全的服务/模块实例访问

```python
@router(prefix="/api", deps=[DBService, MyService])
class Router:
    db_service: DBService
    my_service: MyService

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(AppConfig)
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
| `@router` | `@router(prefix="/api/users")` 或 `@router(prefix="/api/users", deps=[Svc])` |
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
