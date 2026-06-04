# HTTP 路由

Canary Framework 与 Starlette 集成，提供强大的 Web 路由功能和自动参数绑定。

## 定义路由

使用 `@router()` 装饰器定义路由：

```python
from canary_framework import router
from canary_framework.core.router import RouterBase

@router(prefix="/api")
class Api(RouterBase):
    pass
```

### 路由参数

- `prefix`：（可选）应用于此路由中所有路由的 URL 前缀
- `tags`：（可选）用于文档的 OpenAPI 标签。使用关键字参数：`tags=["Users"]`
- 名称从类名自动生成（`ClassName` + `"Router"`）
- 依赖通过类型注解声明

## HTTP 方法装饰器

使用 HTTP 方法装饰器定义路由处理器：

```python
from canary_framework import router, get, post, put, delete, patch
from canary_framework.core.router import RouterBase

@router(prefix="/items")
class Items(RouterBase):
    @get("/")
    async def list_items(self):
        return {"items": []}

    @get("/{item_id}")
    async def get_item(self, item_id: int):
        return {"item_id": item_id}

    @post("/")
    async def create_item(self, body: dict):
        return body, 201

    @put("/{item_id}")
    async def update_item(self, item_id: int, body: dict):
        return {"id": item_id, **body}

    @patch("/{item_id}")
    async def patch_item(self, item_id: int, body: dict):
        return {"id": item_id, **body}

    @delete("/{item_id}")
    async def delete_item(self, item_id: int):
        return {"message": f"Item {item_id} deleted"}
```

路由处理器**不**接收 `request` 参数。参数从 URL 和请求体自动绑定。

## 路径参数

路由模式中的路径参数自动绑定到函数参数：

```python
@router(prefix="/users")
class Users(RouterBase):
    @get("/users/{user_id}")
    async def get_user(self, user_id: int):
        # user_id 从 URL 路径自动绑定
        return {"user_id": user_id}

    @get("/users/{user_id}/posts/{post_id}")
    async def get_user_post(self, user_id: int, post_id: int):
        # 两个参数均自动绑定
        return {"user_id": user_id, "post_id": post_id}
```

## 查询参数

查询参数定义为函数参数（非路径参数）：

```python
@router(prefix="/search")
class Search(RouterBase):
    @get("/search")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        # q、page、limit 从查询字符串自动绑定
        return {
            "query": q,
            "page": page,
            "limit": limit
        }
```

查询参数在 URL 中未提供时使用其默认值。

## 请求体

在路由装饰器上使用 `request_model` 自动解析请求体：

```python
@router(prefix="/data")
class Data(RouterBase):
    @post("/submit")
    async def submit(self, body: dict):
        # 原始请求体解析为 dict
        return {"received": body}
```

当指定 `request_model` 时，请求体解析为 Pydantic 模型并作为 `body` 参数传入：

```python
from pydantic import BaseModel

class CreateItem(BaseModel):
    name: str
    price: float

@post("/", request_model=CreateItem)
async def create(self, body: CreateItem):
    # body 是已验证的 CreateItem 实例
    return {"name": body.name, "price": body.price}
```

## 路由依赖

依赖通过类型注解声明 — 无需 `deps` 列表：

```python
@service()
class UserService(ServiceBase):
    async def get_user(self, user_id):
        return {"id": user_id, "name": "User"}

@router(prefix="/users")
class Users(RouterBase):
    user: UserService  # 自动注入

    @get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await self.user.get_user(user_id)
        return user
```

## 挂载路由

当您在模块中包含路由时，它会自动挂载在其 prefix 上：

```python
@module(services=[Users, Items])
class App(ModuleBase):
    pass

# Users 路由挂载在 prefix="/users"
# Items 路由挂载在 prefix="/items"
```

## OpenAPI 文档

Canary Framework 自动集成 Swagger UI 和 ReDoc，无需任何配置。

### 访问文档

启动应用后，可以访问以下端点：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`
- **OpenAPI JSON**：`http://localhost:8000/openapi.json`

### HTTP 装饰器的 OpenAPI 参数

HTTP 方法装饰器支持以下 OpenAPI 文档参数：

| 参数 | 类型 | 描述 |
|------|------|------|
| `summary` | str | 操作的简短摘要 |
| `description` | str | 操作的详细描述 |
| `request_model` | Pydantic BaseModel | 请求体数据模型（自动解析） |
| `response_model` | Pydantic BaseModel | 响应数据模型 |
| `responses` | dict | 自定义响应定义 |
| `tags` | list[str] | API 分组标签 |
| `deprecated` | bool | 此操作是否已弃用 |
| `operation_id` | str | 唯一操作标识符 |
| `path_params` | dict | 路径参数定义（用于 OpenAPI schema 补充） |
| `query_params` | dict | 查询参数定义（用于 OpenAPI schema 补充） |

### 使用示例

```python
from pydantic import BaseModel, Field
from canary_framework import router, get, post, put, delete

class UserRequest(BaseModel):
    name: str = Field(description="User name")
    email: str = Field(description="User email")

class UserResponse(BaseModel):
    id: int = Field(description="User ID")
    name: str = Field(description="User name")
    email: str = Field(description="User email")

@router(prefix="/users", tags=["Users"])
class Users(RouterBase):
    @get("/",
         summary="List users",
         description="Get all users in the system",
         tags=["Users", "List"],
         query_params={
             "page": {"type": "int", "description": "Page number", "required": False},
             "limit": {"type": "int", "description": "Items per page", "required": False}
         })
    async def list_users(self, page: int = 1, limit: int = 10):
        return {"page": page, "limit": limit, "users": []}

    @get("/{user_id}",
         summary="Get user",
         description="Get user details by user ID",
         response_model=UserResponse,
         path_params={"user_id": {"type": "int", "description": "User ID"}})
    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "John", "email": "john@example.com"}

    @post("/",
          summary="Create user",
          description="Create a new user",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, body: UserRequest):
        return {"id": 1, **body.model_dump()}, 201

    @put("/{user_id}",
         summary="Update user",
         description="Update user information",
         request_model=UserRequest,
         response_model=UserResponse,
         path_params={"user_id": {"type": "int", "description": "User ID"}})
    async def update_user(self, user_id: int, body: UserRequest):
        return {"id": user_id, **body.model_dump()}

    @delete("/{user_id}",
            summary="Delete user",
            description="Delete a specified user",
            path_params={"user_id": {"type": "int", "description": "User ID"}})
    async def delete_user(self, user_id: int):
        return {"message": "User deleted"}
```

### 请求模型自动解析

使用 `request_model` 时：
1. 请求体自动解析为指定的 Pydantic 模型
2. 模型实例作为 `body` 参数传递给处理器
3. 验证由 Pydantic 自动执行

### Tags 分组

路由级别和方法级别的 tags 自动合并：

```python
@router(prefix="/api", tags=["API"])
class Api(RouterBase):
    @get("/users", tags=["Users"])
    async def get_users(self):
        # 合并后的 tags：["API", "Users"]
        pass
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

@router(prefix="")
class Static(RouterBase):
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

@router(prefix="/ws")
class WebSocketEndpoint(RouterBase):
    @get("/ws")
    async def websocket_endpoint(self, websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
```

## 完整示例

```python
from canary_framework import module, service, router, get, post, put, delete
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase
from pydantic import BaseModel, Field
from typing import List

class TodoResponse(BaseModel):
    id: int = Field(description="Todo ID")
    title: str = Field(description="Title")
    completed: bool = Field(description="Whether completed")

class TodoCreate(BaseModel):
    title: str = Field(description="Title")
    completed: bool = Field(description="Whether completed", default=False)

@service()
class DataStore(ServiceBase):
    def __init__(self):
        self.todos: List[dict] = []

    async def get_all(self):
        return self.todos

    async def get_one(self, todo_id):
        return next((t for t in self.todos if t["id"] == todo_id), None)

    async def create(self, todo):
        todo["id"] = len(self.todos) + 1
        self.todos.append(todo)
        return todo

    async def update(self, todo_id, data):
        todo = await self.get_one(todo_id)
        if todo:
            todo.update(data)
        return todo

    async def delete(self, todo_id):
        self.todos = [t for t in self.todos if t["id"] != todo_id]

@router(prefix="/todos", tags=["Todos"])
class Todos(RouterBase):
    store: DataStore

    @get("/", summary="List todos", description="Get all todos")
    async def list_todos(self):
        todos = await self.store.get_all()
        return {"todos": todos}

    @get("/{todo_id}",
         summary="Get todo",
         description="Get todo by ID",
         response_model=TodoResponse)
    async def get_todo(self, todo_id: int):
        todo = await self.store.get_one(todo_id)
        if todo:
            return todo
        return {"error": "Todo not found"}, 404

    @post("/",
          summary="Create todo",
          description="Create a new todo",
          request_model=TodoCreate,
          response_model=TodoResponse)
    async def create_todo(self, body: TodoCreate):
        todo = await self.store.create(body.model_dump())
        return todo, 201

    @put("/{todo_id}",
         summary="Update todo",
         description="Update todo",
         request_model=TodoCreate,
         response_model=TodoResponse)
    async def update_todo(self, todo_id: int, body: TodoCreate):
        todo = await self.store.update(todo_id, body.model_dump())
        if todo:
            return todo
        return {"error": "Todo not found"}, 404

    @delete("/{todo_id}",
            summary="Delete todo",
            description="Delete todo")
    async def delete_todo(self, todo_id: int):
        await self.store.delete(todo_id)
        return {"message": "Todo deleted"}

@module(services=[DataStore, Todos])
class App(ModuleBase):
    pass
```

## 最佳实践

1. **路由组织**：按功能模块组织路由（如 users、posts、todos）
2. **参数验证**：使用 Pydantic 模型配合 `request_model` 进行请求体验证
3. **类型提示**：为路径和查询参数使用类型注解以实现自动绑定
4. **错误处理**：使用一致的错误响应格式
5. **文档**：为每个路由添加 summary 和 description
6. **标签分组**：使用 tags 对相关 API 进行分组
7. **响应模型**：显式指定 `response_model` 以获得更好的 OpenAPI 文档
