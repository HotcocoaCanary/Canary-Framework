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

## 完整示例

```python
from canary_framework import module, service, router, get, post, put, delete
from typing import Dict, List

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
