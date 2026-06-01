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

## OpenAPI Documentation

Canary Framework automatically integrates Swagger UI and ReDoc with zero configuration.

### Accessing Documentation

After starting the application, you can access these endpoints:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### OpenAPI Parameters for HTTP Decorators

HTTP method decorators support the following OpenAPI documentation parameters:

| Parameter | Type | Description |
|------|------|------|
| `summary` | str | Short summary of the operation |
| `description` | str | Detailed description of the operation |
| `request_model` | Pydantic BaseModel | Request body data model |
| `response_model` | Pydantic BaseModel | Response data model |
| `responses` | dict | Custom response definitions |
| `tags` | list[str] | Tags for API grouping |
| `deprecated` | bool | Whether this operation is deprecated |
| `operation_id` | str | Unique operation identifier |
| `path_params` | dict | Path parameter definitions (name -> {"type": "str", "description": "", "required": true}) |
| `query_params` | dict | Query parameter definitions (name -> {"type": "str", "description": "", "required": false}) |

### Usage Example

```python
from pydantic import BaseModel, Field
from canary_framework import router, get, post, put, delete

# Define request and response models
class UserRequest(BaseModel):
    name: str = Field(description="User name")
    email: str = Field(description="User email")

class UserResponse(BaseModel):
    id: int = Field(description="User ID")
    name: str = Field(description="User name")
    email: str = Field(description="User email")

@router(name="users", prefix="/users", tags=["Users"])
class UsersRouter:
    @get("/", 
         summary="List users", 
         description="Get all users in the system",
         tags=["Users", "List"],
         query_params={
             "page": {"type": "int", "description": "Page number", "required": False},
             "limit": {"type": "int", "description": "Items per page", "required": False}
         })
    async def list_users(self, request):
        return {"users": []}
    
    @get("/{user_id}", 
         summary="Get user",
         description="Get user details by user ID",
         response_model=UserResponse,
         path_params={
             "user_id": {"type": "int", "description": "User ID"}
         })
    async def get_user(self, request):
        user_id = request.path_params["user_id"]
        return {"id": int(user_id), "name": "John", "email": "john@example.com"}
    
    @post("/", 
          summary="Create user",
          description="Create a new user",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, request, user: UserRequest):
        # request_model auto-parses the request body and passes it as the second parameter
        return {"id": 1, **user.model_dump()}, 201
    
    @put("/{user_id}",
         summary="Update user",
         description="Update user information",
         request_model=UserRequest,
         response_model=UserResponse,
         path_params={
             "user_id": {"type": "int", "description": "User ID"}
         })
    async def update_user(self, request, user: UserRequest):
        user_id = int(request.path_params["user_id"])
        return {"id": user_id, **user.model_dump()}
    
    @delete("/{user_id}",
            summary="Delete user",
            description="Delete a specified user",
            path_params={
                "user_id": {"type": "int", "description": "User ID"}
            })
    async def delete_user(self, request):
        return {"message": "User deleted"}
```

### Request Model Auto-Parse

When using `request_model` parameter:
1. Request body is automatically parsed into the specified Pydantic model
2. Model instance is passed as the second parameter to the route handler
3. Data validation is automatically performed

### Path and Query Parameters

- `path_params`: Define path parameter type, description and required status
- `query_params`: Define query parameter type, description and required status
- Path parameters are automatically extracted from path patterns (like `{user_id}`) and added to the OpenAPI Schema


### Tags Grouping

Router-level and method-level tags are automatically merged:

```python
@router(name="api", tags=["API"])
class ApiRouter:
    @get("/users", tags=["Users"])
    async def get_users(self, request):
        # Merged tags: ["API", "Users"]
        pass
```

## Complete Example

```python
from canary_framework import module, service, router, get, post, put, delete
from pydantic import BaseModel, Field
from typing import Dict, List

# Data model
class TodoResponse(BaseModel):
    id: int = Field(description="Todo ID")
    title: str = Field(description="Title")
    completed: bool = Field(description="Whether completed")

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
