# Routers & HTTP

Canary Framework provides decorator-driven HTTP routing built on Starlette, with automatic parameter binding and OpenAPI 3.0.3 documentation generation.

## Defining a Router

Use the `@router()` decorator with a class that inherits from `RouterBase`:

```python
from canary_framework import router, get, post
from canary_framework.core.router import RouterBase

@router(prefix="/api")
class Api(RouterBase):
    @get("/hello")
    async def hello(self):
        return {"message": "Hello"}
```

### Router Parameters

- **`prefix`** (str, default `""`) — URL prefix applied to all routes in this router
- **`tags`** (list[str], keyword-only) — OpenAPI tags for documentation grouping
- Name is auto-generated: `ClassName` + `"Router"`
- Dependencies are declared via type annotations on the class body

## HTTP Method Decorators

Six HTTP method decorators are available: `@get`, `@post`, `@put`, `@delete`, `@patch`.

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
    @get("/{user_id}")
    async def get_user(self, user_id: int):
        # user_id auto-bound from URL path
        return {"user_id": user_id}

    @get("/{user_id}/posts/{post_id}")
    async def get_user_post(self, user_id: int, post_id: int):
        # Both parameters auto-bound
        return {"user_id": user_id, "post_id": post_id}
```

The framework automatically converts string path segments to the declared type (int, float, str, bool).

## Query Parameters

Non-path function parameters with defaults are automatically bound from the query string:

```python
@router(prefix="/search")
class Search(RouterBase):
    @get("/")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        # q, page, limit auto-bound from query string
        return {"query": q, "page": page, "limit": limit}
```

A request to `/search?q=canary&page=2&limit=5` binds `q="canary"`, `page=2`, `limit=5`. Parameters use their default values when not provided.

Query parameters in route paths use the `?param={param}&param2={param2}` syntax:

```python
@get("/search?q={query}&page={page}")
async def search(self, query: str = "", page: int = 1):
    ...
```

## Request Body

Use `request_model` on the HTTP method decorator to auto-parse and validate the request body:

```python
from pydantic import BaseModel, Field

class CreateItem(BaseModel):
    name: str = Field(description="Item name")
    price: float = Field(description="Item price", gt=0)

@router(prefix="/items")
class Items(RouterBase):
    @post("/", request_model=CreateItem)
    async def create(self, body: CreateItem):
        # body is a validated CreateItem instance
        return {"name": body.name, "price": body.price}, 201
```

When `request_model` is specified:
1. Request body is parsed into the specified Pydantic model
2. The validated model instance is passed as the `body` parameter
3. Pydantic validation errors return 422 responses automatically

The `body` parameter name is fixed — when `request_model` is set, the parsed model is always passed as `body`.

## Router Dependencies

Dependencies are declared via type annotations — no `deps` list:

```python
@service()
class UserService(ServiceBase):
    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "User"}

@router(prefix="/users")
class Users(RouterBase):
    user_svc: UserService  # Auto-injected

    @get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await self.user_svc.get_user(user_id)
        return user
```

## Mounting Routers

When you include a router in a module's `services` list, it is automatically mounted at its prefix:

```python
@module(services=[Users, Items, Auth])
class App(ModuleBase):
    pass

# Mounted:
# Users  → prefix="/users"
# Items  → prefix="/items"
# Auth   → prefix="/auth"
```

## Root Routes

Routers contribute documentation endpoints at the module's root level. The first router in a module registers:

- **`GET /docs`** — Swagger UI
- **`GET /redoc`** — ReDoc
- **`GET /openapi.json`** — OpenAPI 3.0.3 schema

These paths are configurable via `CanaryConfig` (see [Configuration](./configuration.md)). Documentation is auto-enabled by default — no `docs=True` parameter needed.

On startup, the first router collects `RouterMeta` from all sibling routers in the parent registry and generates a unified OpenAPI schema covering all routes. If multiple routers are in the same module, only the first one registers docs (first-wins behavior tracked via `_cf_docs_registered`).

## OpenAPI Documentation Parameters

HTTP method decorators support the following OpenAPI documentation parameters:

| Parameter | Type | Description |
|---|---|---|
| `summary` | `str` | Short summary of the operation |
| `description` | `str` | Detailed description |
| `request_model` | `BaseModel` | Pydantic model for request body (auto-parsed) |
| `response_model` | `BaseModel` | Pydantic model for response schema |
| `responses` | `dict` | Custom response definitions |
| `tags` | `list[str]` | Tags for API grouping |
| `deprecated` | `bool` | Whether this operation is deprecated |
| `operation_id` | `str` | Unique operation identifier |
| `path_params` | `dict` | Path parameter definitions (schema enrichment) |
| `query_params` | `dict` | Query parameter definitions (schema enrichment) |

## Tags Grouping

Router-level and method-level tags are automatically merged:

```python
@router(prefix="/api", tags=["API"])
class Api(RouterBase):
    @get("/users", tags=["Users"])
    async def get_users(self):
        return {"users": []}
    # Merged tags: ["API", "Users"]
```

## Complete Example

```python
from pydantic import BaseModel, Field
from canary_framework import module, service, router, get, post, put, delete
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase

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

@router(prefix="/todos", tags=["Todos"])
class Todos(RouterBase):
    store: DataStore

    @get("/", summary="List todos", description="Get all todos")
    async def list_todos(self):
        todos = await self.store.get_all()
        return {"todos": todos}

    @get("/{todo_id}", summary="Get todo", response_model=TodoResponse)
    async def get_todo(self, todo_id: int):
        todo = await self.store.get_one(todo_id)
        return todo if todo else ({"error": "Not found"}, 404)

    @post("/", summary="Create todo", request_model=TodoCreate, response_model=TodoResponse)
    async def create_todo(self, body: TodoCreate):
        todo = await self.store.create(body.model_dump())
        return todo, 201

    @put("/{todo_id}", summary="Update todo", request_model=TodoCreate, response_model=TodoResponse)
    async def update_todo(self, todo_id: int, body: TodoCreate):
        todo = await self.store.update(todo_id, body.model_dump())
        return todo if todo else ({"error": "Not found"}, 404)

    @delete("/{todo_id}", summary="Delete todo")
    async def delete_todo(self, todo_id: int):
        await self.store.delete(todo_id)
        return {"message": "Todo deleted"}

@module(services=[DataStore, Todos])
class App(ModuleBase):
    pass
```

## Best Practices

1. **Route Organization**: Organize routes by feature (users, posts, todos) using separate router classes
2. **Parameter Validation**: Use Pydantic models with `request_model` for request body validation
3. **Type Hints**: Use type annotations for path and query parameters for automatic binding
4. **Error Handling**: Return consistent `(data, status_code)` tuples and use `response_model` for schema documentation
5. **Documentation**: Add `summary` and `description` to each route for auto-generated OpenAPI docs
6. **Tag Grouping**: Use tags at both router and method level for clear API grouping
7. **Response Models**: Explicitly specify `response_model` for accurate OpenAPI schema documentation
