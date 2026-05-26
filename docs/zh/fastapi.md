# FastAPI 集成

`canary_framework.web.fastapi` 子包提供 `@router`、HTTP 方法装饰器和 `WebCanary`，用于 FastAPI + Uvicorn 集成。

## 最小 Web 应用

一个单独的 `@router` 类直接传给 `WebCanary`：

```python
from canary_framework.web.fastapi import WebCanary, router, get

@router(prefix="/")
class RootRouter:
    @get("/health")
    async def health(self) -> dict[str, str]:
        return {"status": "ok"}

app = WebCanary(RootRouter)
await app.init()
await app.start()  # 在 127.0.0.1:8000 启动 Uvicorn
```

## 完整示例：带依赖的路由

```python
from canary_framework import module, service, on_init
from canary_framework.web.fastapi import WebCanary, router, get, post

@service(name="user_service")
class UserService:
    users: list[dict] = []

    def list_users(self) -> list[dict]:
        return self.users

    def create_user(self, name: str) -> dict:
        user = {"name": name}
        self.users.append(user)
        return user

@router(prefix="/api/users", deps=[UserService], tags=["users"])
class UserRouter:
    user_service: UserService

    @get("/")
    async def list_users(self) -> list[dict]:
        return self.user_service.list_users()

    @post("/", status_code=201)
    async def create_user(self, body: dict) -> dict:
        return self.user_service.create_user(body["name"])

@module(name="app", services=[UserService, UserRouter])
class AppModule:
    pass

app = WebCanary(AppModule)
await app.init()
await app.start()
```

## HTTP 方法装饰器

| 装饰器 | HTTP 方法 | 示例 |
|--------|-----------|------|
| `@get(path)` | GET | `@get("/users/{id}")` |
| `@post(path)` | POST | `@post("/users", status_code=201)` |
| `@put(path)` | PUT | `@put("/users/{id}")` |
| `@delete(path)` | DELETE | `@delete("/users/{id}")` |
| `@patch(path)` | PATCH | `@patch("/users/{id}")` |

每个装饰器接受以下可选关键字参数：

`response_model`、`status_code`、`summary`、`description`、`tags`、`dependencies`、`deprecated`、`response_description`

这些参数直接映射到 FastAPI 的路由参数 —— 无需学习不同的 API。

## Router 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `prefix` | `str` | 应用于该组所有路由的 URL 前缀 |
| `name` | `str` | 服务名称（省略时通过 `to_snake` 自动生成） |
| `deps` | `list[type]` | 通过 DI 注入的依赖 |
| `tags` | `list[str]` | 应用于所有路由的 OpenAPI 标签 |

## 配置前缀

通过 pydantic `BaseModel` 传入配置。带有 `uvicorn_` 或 `fastapi_` 前缀的字段会被自动路由：

```python
from pydantic import BaseModel

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"
    database_url: str = "postgresql://"  # 无前缀 → 业务配置

app = WebCanary(AppModule)
await app.config(config=AppConfig())
await app.init()
await app.start()
```

## HTTP 请求日志

`WebCanary` 使用 CF 日志格式配置 Uvicorn 的访问日志：

```
[CF] [INFO ] [cf.web] 127.0.0.1:52341 - "GET /api/users HTTP/1.1" 200
[CF] [INFO ] [cf.web] 127.0.0.1:52342 - "POST /api/users HTTP/1.1" 201
```

零开销 —— 日志由 Uvicorn 在协议层生成。
