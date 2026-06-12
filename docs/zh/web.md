# HTTP 路由

Canary Framework 提供基于 Starlette 的装饰器驱动 HTTP 路由，支持自动参数绑定和 OpenAPI 3.0.3 文档生成。

## 定义路由

使用 `@service()` 装饰器，类继承 `ServiceBase`，并声明一个 `Router` 类属性：

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Api(ServiceBase):
    router = Router(prefix="/api")

    @router.get("/hello")
    async def hello(self):
        return {"message": "Hello"}
```

### Router 构造参数

`Router` 类接受以下构造参数：

- **`prefix`**（str，默认 `""`）— 应用于此 Router 中所有路由的 URL 前缀
- **`tags`**（list[str]，仅关键字）— 用于文档分组的 OpenAPI 标签
- 名称从服务类名自动派生
- 依赖通过类体上的类型注解声明

## HTTP 方法装饰器

`Router` 实例提供六个 HTTP 方法装饰器：`.get()`、`.post()`、`.put()`、`.delete()`、`.patch()`。

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Items(ServiceBase):
    router = Router(prefix="/items")

    @router.get("/")
    async def list_items(self):
        return {"items": []}

    @router.get("/{item_id}")
    async def get_item(self, item_id: int):
        return {"item_id": item_id}

    @router.post("/")
    async def create_item(self, body: dict):
        return body, 201

    @router.put("/{item_id}")
    async def update_item(self, item_id: int, body: dict):
        return {"id": item_id, **body}

    @router.patch("/{item_id}")
    async def patch_item(self, item_id: int, body: dict):
        return {"id": item_id, **body}

    @router.delete("/{item_id}")
    async def delete_item(self, item_id: int):
        return {"message": f"Item {item_id} deleted"}
```

路由处理器**不**接收 `request` 参数。参数从 URL 和请求体自动绑定。

## 路径参数

路由模式中的路径参数自动绑定到函数参数：

```python
@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        # user_id 从 URL 路径自动绑定
        return {"user_id": user_id}

    @router.get("/{user_id}/posts/{post_id}")
    async def get_user_post(self, user_id: int, post_id: int):
        # 两个参数均自动绑定
        return {"user_id": user_id, "post_id": post_id}
```

框架自动将字符串路径段转换为声明的类型（int、float、str、bool）。

## 查询参数

非路径函数参数（带默认值）自动从查询字符串绑定：

```python
@service()
class Search(ServiceBase):
    router = Router(prefix="/search")

    @router.get("/")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        # q、page、limit 从查询字符串自动绑定
        return {"query": q, "page": page, "limit": limit}
```

请求 `/search?q=canary&page=2&limit=5` 绑定 `q="canary"`、`page=2`、`limit=5`。参数未提供时使用其默认值。

路由路径中的查询参数使用 `?param={param}&param2={param2}` 语法：

```python
@service()
class Search(ServiceBase):
    router = Router(prefix="/search")

    @router.get("/search?q={query}&page={page}")
    async def search(self, query: str = "", page: int = 1):
        ...
```

## 请求体

在 HTTP 方法装饰器上使用 `request_model` 自动解析和验证请求体：

```python
from pydantic import BaseModel, Field

class CreateItem(BaseModel):
    name: str = Field(description="Item name")
    price: float = Field(description="Item price", gt=0)

@service()
class Items(ServiceBase):
    router = Router(prefix="/items")

    @router.post("/", request_model=CreateItem)
    async def create(self, body: CreateItem):
        # body 是已验证的 CreateItem 实例
        return {"name": body.name, "price": body.price}, 201
```

当指定 `request_model` 时：
1. 请求体解析为指定的 Pydantic 模型
2. 已验证的模型实例作为 `body` 参数传入
3. Pydantic 验证错误自动返回 422 响应

`body` 参数名是固定的 — 设置 `request_model` 时，解析后的模型始终作为 `body` 传入。

## 服务依赖

依赖通过类型注解声明 — 无需 `deps` 列表：

```python
@service()
class UserService(ServiceBase):
    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "User"}

@service()
class Users(ServiceBase):
    router = Router(prefix="/users")
    user_svc: UserService  # 自动注入

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await self.user_svc.get_user(user_id)
        return user
```

## 挂载路由

当您在模块的 `services` 列表中包含一个带 `router` 属性的服务时，它会自动挂载在其 prefix 上：

```python
@module(services=[Users, Items, Auth])
class App(ModuleBase):
    pass

# 挂载：
# Users  → prefix="/users"
# Items  → prefix="/items"
# Auth   → prefix="/auth"
```

## 根路由

Router 在模块根级别贡献文档端点。模块中的第一个 Router 注册：

- **`GET /docs`** — Swagger UI
- **`GET /redoc`** — ReDoc
- **`GET /openapi.json`** — OpenAPI 3.0.3 schema

这些路径可通过 `CanaryConfig` 配置（参见[配置](./configuration.md)）。文档默认自动启用 — 无需 `docs=True` 参数。

启动时，第一个 Router 从父注册表中的所有同级 Router 收集 `RouterMeta`，生成涵盖所有路由的统一 OpenAPI schema。如果同一模块中有多个 Router，只有第一个注册文档端点（通过 `_cf_docs_registered` 跟踪的先到先得行为）。

## OpenAPI 文档参数

HTTP 方法装饰器支持以下 OpenAPI 文档参数：

| 参数 | 类型 | 描述 |
|------|------|------|
| `summary` | `str` | 操作的简短摘要 |
| `description` | `str` | 操作的详细描述 |
| `request_model` | `BaseModel` | 请求体的 Pydantic 模型（自动解析） |
| `response_model` | `BaseModel` | 响应的 Pydantic 模型 |
| `responses` | `dict` | 自定义响应定义 |
| `tags` | `list[str]` | API 分组标签 |
| `deprecated` | `bool` | 此操作是否已弃用 |
| `operation_id` | `str` | 唯一操作标识符 |
| `path_params` | `dict` | 路径参数定义（schema 补充） |
| `query_params` | `dict` | 查询参数定义（schema 补充） |

## Tags 分组

Router 级别和方法级别的 tags 自动合并：

```python
@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["API"])

    @router.get("/users", tags=["Users"])
    async def get_users(self):
        return {"users": []}
    # 合并后的 tags：["API", "Users"]
```

## 中间件支持

在模块中定义中间件来处理请求和响应：

```python
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print(f"Request: {request.method} {request.url}")
        response = await call_next(request)
        print(f"Response status: {response.status_code}")
        return response

@module(services=[Todos])
class App(ModuleBase):
    def __init__(self):
        self.middleware = [CustomMiddleware]
```

## 静态文件

您可以轻松提供静态文件：

```python
from starlette.staticfiles import StaticFiles

@service()
class Static(ServiceBase):
    def __init__(self):
        self.asgi_app = StaticFiles(directory="static", html=True)

@module(services=[Static, Api])
class App(ModuleBase):
    pass
```

## CORS 支持

使用 Starlette 的 CORS 中间件：

```python
from starlette.middleware.cors import CORSMiddleware

@module(services=[Api])
class App(ModuleBase):
    def __init__(self):
        self.middleware = [
            CORSMiddleware(
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
```

## WebSocket 支持

Canary Framework 支持 WebSocket：

```python
from starlette.websockets import WebSocket

@service()
class WebSocketEndpoint(ServiceBase):
    router = Router(prefix="/ws")

    @router.get("/ws")
    async def websocket_endpoint(self, websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
```

## 完整示例

```python
from pydantic import BaseModel, Field
from canary_framework import module, service
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router

class TodoResponse(BaseModel):
    id: int = Field(description="Todo ID")
    title: str = Field(description="Title")
    completed: bool = Field(description="Whether completed")

class TodoCreate(BaseModel):
    title: str = Field(description="Title")
    completed: bool = Field(default=False, description="Whether completed")

@service()
class DataStore(ServiceBase):
    def __init__(self):
        self.todos: list[dict] = []

    async def get_all(self):
        return self.todos

    async def get_one(self, todo_id: int):
        return next((t for t in self.todos if t["id"] == todo_id), None)

    async def create(self, todo: dict):
        todo["id"] = len(self.todos) + 1
        self.todos.append(todo)
        return todo

    async def update(self, todo_id: int, data: dict):
        todo = await self.get_one(todo_id)
        if todo:
            todo.update(data)
        return todo

    async def delete(self, todo_id: int):
        self.todos = [t for t in self.todos if t["id"] != todo_id]

@service()
class Todos(ServiceBase):
    router = Router(prefix="/todos", tags=["Todos"])
    store: DataStore

    @router.get("/", summary="List todos", description="Get all todos")
    async def list_todos(self):
        todos = await self.store.get_all()
        return {"todos": todos}

    @router.get("/{todo_id}", summary="Get todo", response_model=TodoResponse)
    async def get_todo(self, todo_id: int):
        todo = await self.store.get_one(todo_id)
        return todo if todo else ({"error": "Not found"}, 404)

    @router.post("/", summary="Create todo", request_model=TodoCreate, response_model=TodoResponse)
    async def create_todo(self, body: TodoCreate):
        todo = await self.store.create(body.model_dump())
        return todo, 201

    @router.put("/{todo_id}", summary="Update todo", request_model=TodoCreate, response_model=TodoResponse)
    async def update_todo(self, todo_id: int, body: TodoCreate):
        todo = await self.store.update(todo_id, body.model_dump())
        return todo if todo else ({"error": "Not found"}, 404)

    @router.delete("/{todo_id}", summary="Delete todo")
    async def delete_todo(self, todo_id: int):
        await self.store.delete(todo_id)
        return {"message": "Todo deleted"}

@module(services=[DataStore, Todos])
class App(ModuleBase):
    pass
```

## 最佳实践

1. **路由组织**：按功能模块组织路由（如 users、posts、todos），每个使用独立的 service 类，各自拥有 `Router` 属性
2. **参数验证**：使用 Pydantic 模型配合 `request_model` 进行请求体验证
3. **类型提示**：为路径和查询参数使用类型注解以实现自动绑定
4. **错误处理**：返回一致的 `(data, status_code)` 元组，并使用 `response_model` 进行 schema 文档化
5. **文档**：为每个路由添加 `summary` 和 `description` 以自动生成 OpenAPI 文档
6. **标签分组**：在 Router 级别和方法级别使用 tags 以获得清晰的 API 分组
7. **响应模型**：显式指定 `response_model` 以获得准确的 OpenAPI schema 文档
