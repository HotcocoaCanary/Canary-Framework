# Web Routing

Canary Framework integrates with Starlette to provide powerful web routing with automatic parameter binding.

## Defining a Router

Use the `@router()` decorator to define a router:

```python
from canary_framework import router
from canary_framework.core.router import RouterBase

@router(prefix="/api")
class Api(RouterBase):
    pass
```

### Router Parameters

- `prefix`: (optional) URL prefix applied to all routes in this router
- `tags`: (optional) OpenAPI tags for documentation. Use keyword argument: `tags=["Users"]`
- Name is auto-generated from the class name (`ClassName` + `"Router"`)
- Dependencies are declared via type annotations

## HTTP Method Decorators

Use the HTTP method decorators to define route handlers:

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

Route handlers do **not** receive a `request` parameter. Parameters are auto-bound from the URL and request body.

## Path Parameters

Path parameters in the route pattern are automatically bound to function parameters:

```python
@router(prefix="/users")
class Users(RouterBase):
    @get("/users/{user_id}")
    async def get_user(self, user_id: int):
        # user_id auto-bound from URL path
        return {"user_id": user_id}

    @get("/users/{user_id}/posts/{post_id}")
    async def get_user_post(self, user_id: int, post_id: int):
        # Both parameters auto-bound
        return {"user_id": user_id, "post_id": post_id}
```

## Query Parameters

Query parameters are defined as function parameters (not path parameters):

```python
@router(prefix="/search")
class Search(RouterBase):
    @get("/search")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        # q, page, limit auto-bound from query string
        return {
            "query": q,
            "page": page,
            "limit": limit
        }
```

Query parameters use their default values when not provided in the URL.

## Request Body

Use `request_model` on the route decorator to auto-parse the request body:

```python
@router(prefix="/data")
class Data(RouterBase):
    @post("/submit")
    async def submit(self, body: dict):
        # Raw body parsed as dict
        return {"received": body}
```

When `request_model` is specified, the body is parsed into the Pydantic model and passed as the `body` parameter:

```python
from pydantic import BaseModel

class CreateItem(BaseModel):
    name: str
    price: float

@post("/", request_model=CreateItem)
async def create(self, body: CreateItem):
    # body is a validated CreateItem instance
    return {"name": body.name, "price": body.price}
```

## Router Dependencies

Dependencies are declared via type annotations — no `deps` list:

```python
@service()
class UserService(ServiceBase):
    async def get_user(self, user_id):
        return {"id": user_id, "name": "User"}

@router(prefix="/users")
class Users(RouterBase):
    user: UserService  # Auto-injected

    @get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await self.user.get_user(user_id)
        return user
```

## Mounting Routers

When you include a router in a module, it's automatically mounted at its prefix:

```python
@module(services=[Users, Items])
class App(ModuleBase):
    pass

# Users router at prefix="/users"
# Items router at prefix="/items"
```

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
| `request_model` | Pydantic BaseModel | Request body data model (auto-parsed) |
| `response_model` | Pydantic BaseModel | Response data model |
| `responses` | dict | Custom response definitions |
| `tags` | list[str] | Tags for API grouping |
| `deprecated` | bool | Whether this operation is deprecated |
| `operation_id` | str | Unique operation identifier |
| `path_params` | dict | Path parameter definitions (for OpenAPI schema enrichment) |
| `query_params` | dict | Query parameter definitions (for OpenAPI schema enrichment) |

### Usage Example

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
class Users(RouterBase):    @get("/",
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

### Request Model Auto-Parse

When using `request_model`:
1. Request body is automatically parsed into the specified Pydantic model
2. Model instance is passed as the `body` parameter to the handler
3. Validation is automatically performed by Pydantic

### Tags Grouping

Router-level and method-level tags are automatically merged:

```python
@router(prefix="/api", tags=["API"])
class Api(RouterBase):
    @get("/users", tags=["Users"])
    async def get_users(self):
        # Merged tags: ["API", "Users"]
        pass
```

## Middleware Support

Define middleware in modules to handle requests and responses:

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

## Static Files

You can easily serve static files:

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

## CORS Support

Use Starlette's CORS middleware:

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

## WebSocket Support

Canary Framework supports WebSocket:

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

## Complete Example

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

## Best Practices

1. **Route Organization**: Organize routes by feature modules (e.g., users, posts, todos)
2. **Parameter Validation**: Use Pydantic models for request body validation with `request_model`
3. **Type Hints**: Use type annotations for path and query parameters for automatic binding
4. **Error Handling**: Use consistent error response format
5. **Documentation**: Add summary and description to each route
6. **Tag Grouping**: Use tags to group related APIs
7. **Response Models**: Explicitly specify `response_model` for better OpenAPI documentation
