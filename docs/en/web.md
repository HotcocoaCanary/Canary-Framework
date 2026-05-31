# Web Routing

Canary Framework integrates with Starlette to provide powerful web routing capabilities.

## Defining a Router

Use the `@router` decorator to define a router:

```python
from canary_framework import router

@router(name="api", prefix="/api")
class ApiRouter:
    pass
```

### Router Parameters

- `name`: (required) A unique identifier for the router
- `prefix`: (optional) URL prefix applied to all routes in this router
- `deps`: (optional) List of services this router depends on
- `tags`: (optional) OpenAPI tags for documentation

## HTTP Method Decorators

Use the HTTP method decorators to define route handlers:

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

## Request Handling

Route handlers receive a Starlette `Request` object and can return various types:

```python
from starlette.responses import JSONResponse, PlainTextResponse, HTMLResponse

@router(name="responses")
class ResponseExamples:
    @get("/dict")
    async def return_dict(self, request):
        # Automatically converted to JSONResponse
        return {"message": "Hello"}
    
    @get("/str")
    async def return_str(self, request):
        # Automatically converted to PlainTextResponse
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

## Path Parameters

Use Starlette's path parameter syntax:

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

## Query Parameters

Access query parameters through the request object:

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

## Request Body

Parse JSON request bodies:

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

## Router Dependencies

Routers can depend on services:

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
        # UserService is injected as self.user_service
        user = await self.user_service.get_user(user_id)
        return user
```

## Mounting Routers

When you include a router in a module, it's automatically mounted:

```python
@module(name="app", services=[UsersRouter, ItemsRouter])
class AppModule:
    pass
```

Routers are mounted at paths based on their names:
- `UsersRouter(name="users")` → `/users`
- `ItemsRouter(name="items")` → `/items`

## Complete Example

```python
from canary_framework import module, service, router, get, post, put, delete
from typing import Dict, List

# Data store (in-memory)
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

# Todo router
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

# Main app
@module(name="app", services=[DataStore, TodosRouter])
class AppModule:
    pass
```
