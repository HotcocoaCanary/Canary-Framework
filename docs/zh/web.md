# Web 路由

Canary 框架与 Starlette 集成，提供强大的 Web 路由功能。

## 定义路由

使用 `@router` 装饰器定义路由。类必须显式继承 `RouterBase`。路由名称自动生成为 `类名 + "Router"`：

```python
from canary_framework import router
from canary_framework.core import RouterBase

@router(prefix="/api")
class ApiRouter(RouterBase):
    pass
```

### 路由参数

- `prefix`：URL 前缀（位置参数，默认空字符串）。应用于此路由中所有路由的 URL 前缀
- `tags`：（可选，仅关键字参数）用于文档的 OpenAPI 标签列表

> 注意：旧的 `name` 和 `deps` 参数已移除。名称自动生成，依赖通过类型注解声明。

### 自动命名

路由名称自动生成为 `类名 + "Router"`：

| 类名 | 自动生成的路由名 |
|------|-----------------|
| `Api` | `ApiRouter` |
| `Users` | `UsersRouter` |
| `Todos` | `TodosRouter` |

## HTTP 方法装饰器

使用 HTTP 方法装饰器定义路由处理程序。**重要**：路由处理器不再需要 `request` 参数 — 路径参数、查询参数和请求体自动绑定：

```python
from canary_framework import router, get, post, put, delete, patch
from canary_framework.core import RouterBase

@router(prefix="/items")
class ItemsRouter(RouterBase):
    @get("/")
    async def list_items(self):
        return {"items": []}

    @get("/{item_id}")
    async def get_item(self, item_id: int):
        return {"item_id": item_id}

    @post("/")
    async def create_item(self, data: dict):
        return data, 201

    @put("/{item_id}")
    async def update_item(self, item_id: int, data: dict):
        return {"id": item_id, **data}

    @patch("/{item_id}")
    async def patch_item(self, item_id: int, data: dict):
        return {"id": item_id, **data}

    @delete("/{item_id}")
    async def delete_item(self, item_id: int):
        return {"message": f"Item {item_id} deleted"}
```

## 请求处理

路由处理程序可以返回各种类型，框架会自动转换为合适的响应：

```python
from starlette.responses import JSONResponse, PlainTextResponse, HTMLResponse, Response
from canary_framework import router, get
from canary_framework.core import RouterBase

@router()
class ResponseExamples(RouterBase):
    @get("/dict")
    async def return_dict(self):
        # 自动转换为 JSONResponse
        return {"message": "Hello"}

    @get("/str")
    async def return_str(self):
        # 自动转换为 PlainTextResponse
        return "Hello, World!"

    @get("/json-response")
    async def return_json_response(self):
        return JSONResponse({"message": "Hello"}, status_code=200)

    @get("/html")
    async def return_html(self):
        return HTMLResponse("<h1>Hello</h1>")

    @get("/error")
    async def return_error(self):
        return {"error": "Not found"}, 404
```

## 路径参数

路径参数从 URL 模式自动提取并绑定到函数参数：

```python
from canary_framework import router, get
from canary_framework.core import RouterBase

@router()
class UsersRouter(RouterBase):
    @get("/users/{user_id}")
    async def get_user(self, user_id: int):
        return {"user_id": user_id}

    @get("/users/{user_id}/posts/{post_id}")
    async def get_user_post(self, user_id: int, post_id: int):
        return {"user_id": user_id, "post_id": post_id}
```

## 查询参数

查询参数从 URL 自动提取并绑定到函数参数：

```python
from canary_framework import router, get
from canary_framework.core import RouterBase

@router()
class SearchRouter(RouterBase):
    @get("/search")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        return {
            "query": q,
            "page": page,
            "limit": limit
        }
```

查询参数定义在路径后，使用 `?param={param}` 或 `#param={param}` 语法：

```python
from canary_framework import router, get
from canary_framework.core import RouterBase

@router()
class DataRouter(RouterBase):
    @get("/data?page={page}#section={section}")
    async def get_data(self, page: int = 1, section: str = ""):
        return {"page": page, "section": section}
```

## 请求体

使用 `request_model` 参数指定 Pydantic 模型，请求体自动解析并作为函数参数传入：

```python
from pydantic import BaseModel
from canary_framework import router, post
from canary_framework.core import RouterBase

class ItemCreate(BaseModel):
    name: str
    price: float

@router()
class DataRouter(RouterBase):
    @post("/submit")
    async def submit(self, data: dict):
        # 无 request_model 时，将从请求体自动解析为 dict
        return {"received": data}

    @post("/items", request_model=ItemCreate)
    async def create_item(self, item: ItemCreate):
        # request_model 会自动解析请求体为 ItemCreate 实例
        return {"created": item.model_dump()}
```

## 路由依赖

路由通过类型注解声明对服务的依赖：

```python
from canary_framework import service, router, get
from canary_framework.core import ServiceBase, RouterBase

@service()
class UserService(ServiceBase):
    async def get_user(self, user_id):
        return {"id": user_id, "name": "User"}

@router()
class UsersRouter(RouterBase):
    svc: UserService  # 类型注解声明依赖

    @get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await self.svc.get_user(user_id)
        return user
```

## 挂载路由

当您将路由包含在模块的 `services` 列表中时，它会自动挂载。路由根据其服务名称挂载在路径上：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[UsersRouter, ItemsRouter])
class App(ModuleBase):
    pass
```

路由挂载路径对应服务名称：
- `Users` 类 → `UsersRouter` → 挂载在 `/UsersRouter`
- `Items` 类 → `ItemsRouter` → 挂载在 `/ItemsRouter`

## OpenAPI 文档

Canary 框架自动集成 Swagger UI 和 ReDoc，无需额外配置。

### 访问文档

启动应用后，可以访问以下端点：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### HTTP 方法装饰器的 OpenAPI 参数

HTTP 方法装饰器支持以下 OpenAPI 文档参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `summary` | str | 操作的简短摘要 |
| `description` | str | 操作的详细描述 |
| `request_model` | Pydantic BaseModel | 请求体数据模型 |
| `response_model` | Pydantic BaseModel | 响应数据模型 |
| `responses` | dict | 自定义响应定义 |
| `tags` | list[str] | API 分组标签 |
| `deprecated` | bool | 是否弃用 |
| `operation_id` | str | 操作唯一标识符 |

> 注意：`path_params` 和 `query_params` 已不再需要 — 框架自动从函数签名和路径模式中提取参数信息。

### 使用示例

```python
from pydantic import BaseModel, Field
from canary_framework import router, get, post, put, delete
from canary_framework.core import RouterBase

class UserRequest(BaseModel):
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

class UserResponse(BaseModel):
    id: int = Field(description="用户ID")
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

@router(prefix="/users", tags=["Users"])
class UsersRouter(RouterBase):
    @get("/",
         summary="获取用户列表",
         description="获取系统中所有用户的列表",
         tags=["Users", "List"])
    async def list_users(self, page: int = 1, limit: int = 10):
        return {"users": [], "page": page, "limit": limit}

    @get("/{user_id}",
         summary="获取单个用户",
         description="根据用户ID获取用户详细信息",
         response_model=UserResponse)
    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "John", "email": "john@example.com"}

    @post("/",
          summary="创建用户",
          description="创建新用户",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, user: UserRequest):
        return {"id": 1, **user.model_dump()}, 201

    @put("/{user_id}",
         summary="更新用户",
         description="更新用户信息",
         request_model=UserRequest,
         response_model=UserResponse)
    async def update_user(self, user_id: int, user: UserRequest):
        return {"id": user_id, **user.model_dump()}

    @delete("/{user_id}",
            summary="删除用户",
            description="删除指定用户")
    async def delete_user(self, user_id: int):
        return {"message": "User deleted"}
```

### 请求模型自动解析

当使用 `request_model` 参数时：
1. 请求体会自动解析为该 Pydantic 模型
2. 模型实例会作为**第一个参数**传递给路由处理函数
3. 其他参数（路径参数、查询参数）作为关键字参数传递
4. 自动进行数据验证

### Tags 分组

路由级别和方法级别的 tags 会自动合并：

```python
from canary_framework import router, get
from canary_framework.core import RouterBase

@router(tags=["API"])
class ApiRouter(RouterBase):
    @get("/users", tags=["Users"])
    async def get_users(self):
        # 合并后的 tags: ["API", "Users"]
        pass
```

## 中间件支持

您可以通过在模块的 `__init__` 中定义中间件来处理请求和响应：

```python
from starlette.middleware.base import BaseHTTPMiddleware
from canary_framework import module
from canary_framework.core import ModuleBase

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print(f"Request: {request.method} {request.url}")
        response = await call_next(request)
        print(f"Response status: {response.status_code}")
        return response

@module(services=[TodosRouter])
class App(ModuleBase):
    def __init__(self):
        self.middleware = [CustomMiddleware]
```

## CORS 支持

使用 Starlette 的 CORS 中间件：

```python
from starlette.middleware.cors import CORSMiddleware
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[ApiRouter])
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

## 完整示例

```python
from canary_framework import module, service, router, get, post, put, delete
from canary_framework.core import ServiceBase, ModuleBase, RouterBase
from pydantic import BaseModel, Field
from typing import Dict, List

class TodoResponse(BaseModel):
    id: int = Field(description="待办事项ID")
    title: str = Field(description="标题")
    completed: bool = Field(description="是否完成")

class TodoCreate(BaseModel):
    title: str = Field(description="标题")
    completed: bool = Field(description="是否完成", default=False)

@service()
class DataStore(ServiceBase):
    def __init__(self):
        self.todos: List[Dict] = []

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
class TodosRouter(RouterBase):
    store: DataStoreService

    @get("/", summary="获取待办列表", description="获取所有待办事项")
    async def list_todos(self):
        todos = await self.store.get_all()
        return {"todos": todos}

    @get("/{todo_id}",
         summary="获取待办",
         description="根据ID获取待办事项",
         response_model=TodoResponse)
    async def get_todo(self, todo_id: int):
        todo = await self.store.get_one(todo_id)
        if todo:
            return todo
        return {"error": "Todo not found"}, 404

    @post("/",
          summary="创建待办",
          description="创建新的待办事项",
          request_model=TodoCreate,
          response_model=TodoResponse)
    async def create_todo(self, todo: TodoCreate):
        todo = await self.store.create(todo.model_dump())
        return todo, 201

    @put("/{todo_id}",
         summary="更新待办",
         description="更新待办事项",
         request_model=TodoCreate,
         response_model=TodoResponse)
    async def update_todo(self, todo_id: int, todo: TodoCreate):
        todo = await self.store.update(todo_id, todo.model_dump())
        if todo:
            return todo
        return {"error": "Todo not found"}, 404

    @delete("/{todo_id}",
            summary="删除待办",
            description="删除待办事项")
    async def delete_todo(self, todo_id: int):
        await self.store.delete(todo_id)
        return {"message": "Todo deleted"}

@module(services=[DataStoreService, TodosRouter])
class App(ModuleBase):
    pass
```

## 最佳实践

1. **路由组织**：按功能模块组织路由（如 users、posts、todos）
2. **参数验证**：使用 Pydantic 模型进行请求体验证
3. **错误处理**：统一的错误响应格式
4. **文档注释**：为每个路由添加 summary 和 description
5. **标签分组**：使用 tags 对 API 进行分组
6. **响应模型**：明确指定 response_model 以生成更好的 OpenAPI 文档
7. **简洁路由处理器**：利用自动参数绑定，让处理器函数签名简洁清晰
