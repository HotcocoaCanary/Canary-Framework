# Web 路由

Canary 框架与 Starlette 集成，提供强大的 Web 路由功能。

## 定义路由

使用 `@router` 装饰器定义路由：

```python
from canary_framework import router

@router(name="api", prefix="/api")
class ApiRouter:
    pass
```

### 路由参数

- `name`：（必需）路由的唯一标识符
- `prefix`：（可选）应用于此路由中所有路由的 URL 前缀
- `deps`：（可选）此路由依赖的服务列表
- `tags`：（可选）用于文档的 OpenAPI 标签

## HTTP 方法装饰器

使用 HTTP 方法装饰器定义路由处理程序：

```python
from canary_framework import router, get, post, put, delete, patch

@router(name="items", prefix="/items")
class ItemsRouter:
    @get("/")
    async def list_items(self, request):
        return {"items": []}
    
    @get("/{item_id}")
    async def get_item(self, request):
        item_id = request.path_params["item_id"]
        return {"item_id": item_id}
    
    @post("/")
    async def create_item(self, request):
        data = await request.json()
        return data, 201
    
    @put("/{item_id}")
    async def update_item(self, request):
        item_id = request.path_params["item_id"]
        data = await request.json()
        return {"id": item_id, **data}
    
    @patch("/{item_id}")
    async def patch_item(self, request):
        item_id = request.path_params["item_id"]
        data = await request.json()
        return {"id": item_id, **data}
    
    @delete("/{item_id}")
    async def delete_item(self, request):
        item_id = request.path_params["item_id"]
        return {"message": f"Item {item_id} deleted"}
```

## 请求处理

路由处理程序接收一个 Starlette `Request` 对象，并可以返回各种类型：

```python
from starlette.responses import JSONResponse, PlainTextResponse, HTMLResponse

@router(name="responses")
class ResponseExamples:
    @get("/dict")
    async def return_dict(self, request):
        # 自动转换为 JSONResponse
        return {"message": "Hello"}
    
    @get("/str")
    async def return_str(self, request):
        # 自动转换为 PlainTextResponse
        return "Hello, World!"
    
    @get("/json-response")
    async def return_json_response(self, request):
        return JSONResponse({"message": "Hello"}, status_code=200)
    
    @get("/html")
    async def return_html(self, request):
        return HTMLResponse("<h1>Hello</h1>")
    
    @get("/error")
    async def return_error(self, request):
        return {"error": "Not found"}, 404
```

## 路径参数

使用 Starlette 的路径参数语法：

```python
@router(name="users")
class UsersRouter:
    @get("/users/{user_id}")
    async def get_user(self, request):
        user_id = request.path_params["user_id"]
        return {"user_id": user_id}
    
    @get("/users/{user_id}/posts/{post_id}")
    async def get_user_post(self, request):
        user_id = request.path_params["user_id"]
        post_id = request.path_params["post_id"]
        return {"user_id": user_id, "post_id": post_id}
```

## 查询参数

通过请求对象访问查询参数：

```python
@router(name="search")
class SearchRouter:
    @get("/search")
    async def search(self, request):
        query = request.query_params.get("q", "")
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 10))
        return {
            "query": query,
            "page": page,
            "limit": limit
        }
```

## 请求体

解析 JSON 请求体：

```python
@router(name="data")
class DataRouter:
    @post("/submit")
    async def submit(self, request):
        data = await request.json()
        return {"received": data}
    
    @post("/form")
    async def submit_form(self, request):
        form_data = await request.form()
        return {"received": dict(form_data)}
```

## 路由依赖

路由可以依赖服务：

```python
@service(name="user_service")
class UserService:
    async def get_user(self, user_id):
        return {"id": user_id, "name": "User"}

@router(name="users", deps=[UserService])
class UsersRouter:
    @get("/{user_id}")
    async def get_user(self, request):
        user_id = request.path_params["user_id"]
        # UserService 注入为 self.user_service
        user = await self.user_service.get_user(user_id)
        return user
```

## 挂载路由

当您将路由包含在模块中时，它会自动挂载：

```python
@module(name="app", services=[UsersRouter, ItemsRouter])
class AppModule:
    pass
```

路由会根据其名称挂载在路径上：
- `UsersRouter(name="users")` → `/users`
- `ItemsRouter(name="items")` → `/items`

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
| `path_params` | dict | 路径参数定义（名称 -> {"type": "str", "description": "", "required": true}） |
| `query_params` | dict | 查询参数定义（名称 -> {"type": "str", "description": "", "required": false}） |

### 使用示例

```python
from pydantic import BaseModel, Field
from canary_framework import router, get, post, put, delete

# 定义请求和响应模型
class UserRequest(BaseModel):
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

class UserResponse(BaseModel):
    id: int = Field(description="用户ID")
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

@router(name="users", prefix="/users", tags=["Users"])
class UsersRouter:
    @get("/", 
         summary="获取用户列表", 
         description="获取系统中所有用户的列表",
         tags=["Users", "List"],
         query_params={
             "page": {"type": "int", "description": "页码", "required": False},
             "limit": {"type": "int", "description": "每页数量", "required": False}
         })
    async def list_users(self, request):
        return {"users": []}
    
    @get("/{user_id}", 
         summary="获取单个用户",
         description="根据用户ID获取用户详细信息",
         response_model=UserResponse,
         path_params={
             "user_id": {"type": "int", "description": "用户ID"}
         })
    async def get_user(self, request):
        user_id = request.path_params["user_id"]
        return {"id": int(user_id), "name": "John", "email": "john@example.com"}
    
    @post("/", 
          summary="创建用户",
          description="创建新用户",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, request, user: UserRequest):
        # request_model 会自动解析请求体并作为第二个参数传入
        return {"id": 1, **user.model_dump()}, 201
    
    @put("/{user_id}",
         summary="更新用户",
         description="更新用户信息",
         request_model=UserRequest,
         response_model=UserResponse,
         path_params={
             "user_id": {"type": "int", "description": "用户ID"}
         })
    async def update_user(self, request, user: UserRequest):
        user_id = int(request.path_params["user_id"])
        return {"id": user_id, **user.model_dump()}
    
    @delete("/{user_id}",
            summary="删除用户",
            description="删除指定用户",
            path_params={
                "user_id": {"type": "int", "description": "用户ID"}
            })
    async def delete_user(self, request):
        return {"message": "User deleted"}
```

### 请求模型自动解析

当使用 `request_model` 参数时：
1. 请求体会自动解析为该 Pydantic 模型
2. 模型实例会作为第二个参数传递给路由处理函数
3. 自动进行数据验证

### 路径参数和查询参数

- `path_params`：定义路径参数的类型、描述和是否必需
- `query_params`：定义查询参数的类型、描述和是否必需
- 路径参数会从路径模式（如 `{user_id}`）自动提取并添加到 OpenAPI Schema 中


### Tags 分组

路由级别和方法级别的 tags 会自动合并：

```python
@router(name="api", tags=["API"])
class ApiRouter:
    @get("/users", tags=["Users"])
    async def get_users(self, request):
        # 合并后的 tags: ["API", "Users"]
        pass
```

## 完整示例

```python
from canary_framework import module, service, router, get, post, put, delete
from pydantic import BaseModel, Field
from typing import Dict, List

# 数据模型
class TodoResponse(BaseModel):
    id: int = Field(description="待办事项ID")
    title: str = Field(description="标题")
    completed: bool = Field(description="是否完成")
```

# 数据存储（内存中）
@service(name="data_store")
class DataStore:
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

# 待办事项路由
@router(name="todos", prefix="/todos", deps=[DataStore])
class TodosRouter:
    @get("/")
    async def list_todos(self, request):
        todos = await self.data_store.get_all()
        return {"todos": todos}
    
    @get("/{todo_id}")
    async def get_todo(self, request):
        todo_id = int(request.path_params["todo_id"])
        todo = await self.data_store.get_one(todo_id)
        if todo:
            return todo
        return {"error": "Todo not found"}, 404
    
    @post("/")
    async def create_todo(self, request):
        data = await request.json()
        todo = await self.data_store.create(data)
        return todo, 201
    
    @put("/{todo_id}")
    async def update_todo(self, request):
        todo_id = int(request.path_params["todo_id"])
        data = await request.json()
        todo = await self.data_store.update(todo_id, data)
        if todo:
            return todo
        return {"error": "Todo not found"}, 404
    
    @delete("/{todo_id}")
    async def delete_todo(self, request):
        todo_id = int(request.path_params["todo_id"])
        await self.data_store.delete(todo_id)
        return {"message": "Todo deleted"}

# 主应用
@module(name="app", services=[DataStore, TodosRouter])
class AppModule:
    pass
```
