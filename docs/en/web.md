# Routers & HTTP

Canary Framework provides decorator-driven HTTP routing built on Starlette, with automatic parameter binding and OpenAPI 3.0.3 documentation generation.

## Defining Routes

Use the `@service()` decorator with a class that inherits from `ServiceBase`, and declare a `Router` class attribute:

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

### Router Constructor Parameters

The `Router` class accepts the following constructor arguments:

- **`prefix`** (str, default `""`) — URL prefix applied to all routes registered on this router. Combined with each route's path to form the served path (see [Mounting Routers](#mounting-routers)).
- **`tags`** (`list[str]`, keyword-only) — OpenAPI tags automatically applied to every endpoint declared on this router.

!!! tip
    `Router` itself does not know about services or modules — it just accumulates `RouteInfo` entries. A service's `router` attribute is discovered and bound to `self` when routes are assembled (see [Mounting Routers](#mounting-routers)).

## HTTP Method Decorators

Five HTTP method decorators are available on the `Router` instance: `.get()`, `.post()`, `.put()`, `.delete()`, `.patch()`.

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
    async def create_item(self, item: dict):
        return item, 201

    @router.put("/{item_id}")
    async def update_item(self, item_id: int, item: dict):
        return {"id": item_id, **item}

    @router.patch("/{item_id}")
    async def patch_item(self, item_id: int, item: dict):
        return {"id": item_id, **item}

    @router.delete("/{item_id}")
    async def delete_item(self, item_id: int):
        return {"message": f"Item {item_id} deleted"}
```

Route handlers do **not** receive a `request` parameter. Parameters are bound by **name**: path parameters, query parameters, and the request body.

## Path Parameters

Path parameters in the route pattern are automatically bound to function parameters of the same name:

```python
@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        # user_id auto-bound from the URL path
        return {"user_id": user_id}

    @router.get("/{user_id}/posts/{post_id}")
    async def get_user_post(self, user_id: int, post_id: int):
        # Both parameters auto-bound
        return {"user_id": user_id, "post_id": post_id}
```

The framework converts the string path segment to the parameter's declared type (`int`, `float`, `str`, `bool`, and `Optional[T]` of those). An unconvertible value returns **400**.

## Query Parameters

!!! warning "Query params must be declared in the path string"
    Unlike path parameters, a function parameter is **not** treated as a query parameter just because it has a default value. It must also appear in the route's path string using `?key={key}` syntax. A defaulted parameter that is *not* declared there simply keeps its default — it is never read from the query string.

```python
@service()
class Search(ServiceBase):
    router = Router(prefix="/search")

    # q, page, and limit are declared in the path string, so they bind
    # from the query string. Anything else stays at its default.
    @router.get("/?q={q}&page={page}&limit={limit}")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        return {"query": q, "page": page, "limit": limit}
```

A request to `/search?q=canary&page=2&limit=5` binds `q="canary"`, `page=2`, `limit=5`. Parameters keep their default values when omitted from the request.

```python
# WRONG — `active` has a default but is not declared in the path string,
# so it is NEVER bound from the query string; it is always True.
@router.get("/users")
async def list_users(self, active: bool = True):
    ...

# RIGHT — declare it in the path so it binds from ?active=...
@router.get("/users?active={active}")
async def list_users(self, active: bool = True):
    ...
```

A query parameter **without** a default is required: a missing or invalid value returns **422**.

## Request Body

The handler's **body parameter** is the first parameter that is neither a path parameter nor a query parameter (as declared in the path string). It does not have to be named `body`.

```python
from pydantic import BaseModel, Field

class CreateItem(BaseModel):
    name: str = Field(description="Item name")
    price: float = Field(description="Item price", gt=0)

@service()
class Items(ServiceBase):
    router = Router(prefix="/items")

    @router.post("/")
    async def create(self, item: CreateItem):
        # `item` is auto-detected as the request_model (it's a BaseModel
        # subclass, and it's neither a path nor a query param).
        return {"name": item.name, "price": item.price}, 201
```

`request_model` is auto-detected from the first `BaseModel`-typed parameter that isn't a path/query param; you can also pass it explicitly:

```python
    @router.post("/", request_model=CreateItem)
    async def create(self, item: CreateItem):
        ...
```

When a body is expected:

1. The request body is parsed as JSON — invalid JSON returns **400**.
2. It is validated against the resolved `request_model` — a `ValidationError` returns **422**.
3. The validated model instance is passed to the body parameter (by its actual name, whatever that is).

## Service Dependencies

Dependencies are declared via type annotations — no `deps` list:

```python
@service()
class UserService(ServiceBase):
    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "User"}

@service()
class Users(ServiceBase):
    router = Router(prefix="/users")
    user_svc: UserService  # Auto-injected

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await self.user_svc.get_user(user_id)
        return user
```

See [Dependency Injection](./dependency-injection.md) for the full DI mechanism.

## Mounting Routers

!!! warning "Behavior change: explicit prefixes only (D4)"
    Canary uses an **explicit-prefix** model. There is no `/{ServiceName}` auto-namespacing — a router with no `prefix` serves its routes at the bare path. If you were relying on implicit per-service mounting, give each router an explicit `prefix=` to reproduce the old namespacing, e.g. `Router(prefix="/users")`.

A module composes services; it does not "mount" them at a derived path. Each route is served at `router.prefix + route_path` (with repeated `/` collapsed), regardless of whether the owning service runs standalone or nested inside a module tree:

```python
@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        return {"user_id": user_id}

@service()
class Items(ServiceBase):
    router = Router(prefix="/items")

    @router.get("/")
    async def list_items(self):
        return {"items": []}

@module(services=[Users, Items])
class App(ModuleBase):
    pass

# Served paths:
#   GET /users/{user_id}   (Users' own prefix)
#   GET /items/            (Items' own prefix)
```

A module also collects routes recursively from nested modules — the composed tree is flattened into one routing table, with each node contributing its own already-prefixed paths (no additional prefix cascading is applied by the parent).

If two routes resolve to the same `(method, full_path)` anywhere in the tree, assembly raises `ValueError` — this is a real collision check, not a silent override.

```python
@service()
class A(ServiceBase):
    router = Router()  # no prefix

    @router.get("/ping")
    async def ping(self): ...

@service()
class B(ServiceBase):
    router = Router()  # no prefix — collides with A's "/ping"

    @router.get("/ping")
    async def ping(self): ...

@module(services=[A, B])
class App(ModuleBase):
    pass

# app.init() → asgi_app access raises:
#   ValueError: Route collision: GET /ping
```

!!! note "Standalone and module-composed services behave the same way"
    A lone `@service` run directly (`app = MyService(); app.init(); uvicorn.run(app, ...)`) and the same service composed into a module serve identical paths — the only difference is the scope of the subtree being assembled. See `examples/01_standalone.py` vs. `examples/04_module_router.py`.

## Root Routes

Doc endpoints — Swagger UI, ReDoc, and the OpenAPI JSON schema — are generated **once**, at the node you actually run (the "run node"): whichever `ServiceBase`/`ModuleBase` instance you call `.init()` and serve as the ASGI app. Assembly walks the whole subtree under that node, collects every route, checks for collisions, and builds one Starlette routing table plus one OpenAPI document, exposing:

- **`GET /docs`** — Swagger UI
- **`GET /redoc`** — ReDoc
- **`GET /openapi.json`** — OpenAPI 3.0.3 schema

These paths (and the Swagger/ReDoc CDN URLs) are configurable via `CanaryConfig` — see [Documentation Endpoints](./configuration.md#documentation-endpoints). Documentation is on by default; there is no `docs=True` flag to set.

Assembly is lazy and memoized: the first access to `asgi_app` or `openapi()` triggers it, and the result is cached. `ModuleBase.init()` resets that cache, so an access before `init()` can't poison the memoized result with an incomplete tree.

## OpenAPI Documentation Parameters

HTTP method decorators support the following keyword arguments (see `Router` in `core/router/_base.py`):

| Parameter | Type | Description |
|---|---|---|
| `summary` | `str \| None` | Short summary of the operation |
| `description` | `str \| None` | Detailed description |
| `request_model` | `type \| None` | Pydantic model for the request body (auto-parsed and validated) |
| `response_model` | `type \| None` | Pydantic model used for the OpenAPI response schema only |
| `responses` | `dict \| None` | Custom response definitions |
| `tags` | `list[str] \| None` | Tags for API grouping (merged with the router's own tags) |
| `deprecated` | `bool` | Whether this operation is deprecated |
| `operation_id` | `str \| None` | Unique operation identifier |

!!! note
    There are no `path_params` / `query_params` kwargs — path and query parameter schemas are derived automatically from the route's path string and the handler's type annotations.

`response_model` affects OpenAPI documentation only — it does **not** validate or filter the actual response your handler returns.

## Status Codes & Type Coercion

| Situation | Status |
|---|---|
| Invalid path parameter (fails type conversion) | **400** |
| Missing required query parameter, or invalid query value | **422** |
| Invalid/non-JSON request body | **400** |
| Request body fails `request_model` validation | **422** |

Type coercion for path/query values (`_convert_param`): `int`, `float`, `str` convert directly; `Optional[T]` is unwrapped first. For `bool`, the string is lower-cased and matched against:

- `1`, `true`, `yes`, `on` → `True`
- `0`, `false`, `no`, `off` → `False`
- anything else → conversion error → **422** (query) / **400** (path)

## Return Values

Handlers can return several shapes; `_auto_response` converts them:

=== "dict / list"
    ```python
    @router.get("/items")
    async def list_items(self):
        return {"items": [1, 2, 3]}  # → JSONResponse
    ```

=== "Pydantic model"
    ```python
    @router.get("/items/{item_id}")
    async def get_item(self, item_id: int):
        return ItemModel(id=item_id, name="widget")  # → JSONResponse(model_dump())
    ```

=== "(body, status_code) tuple"
    ```python
    @router.post("/items")
    async def create_item(self, item: dict):
        return item, 201  # → JSONResponse(item, status_code=201)
    ```

=== "str"
    ```python
    @router.get("/ping")
    async def ping(self):
        return "pong"  # → PlainTextResponse
    ```

=== "Response"
    ```python
    from starlette.responses import RedirectResponse

    @router.get("/old")
    async def old(self):
        return RedirectResponse("/new")  # → returned as-is
    ```

- A `Response` instance is returned as-is.
- A 2-tuple `(body, status_code)` where `status_code` is an `int` (and not a `bool`) sets the HTTP status; `body` is converted the same way as a top-level return (`Response`, `BaseModel`, `dict`/`list`, `str`, or else stringified).
- A `bool` in the second tuple position is **not** treated as a status code — `(x, True)` is not a status tuple, it falls through to the default (str) conversion path.
- `dict`/`list` (including nested `BaseModel`s inside them) → `JSONResponse`.
- `BaseModel` → `JSONResponse(model_dump())`.
- `str` → `PlainTextResponse`.
- Anything else → `PlainTextResponse(str(result))`.

## Tags Grouping

Router-level and method-level tags are automatically merged:

```python
@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["API"])

    @router.get("/users", tags=["Users"])
    async def get_users(self):
        return {"users": []}
    # Merged tags: ["API", "Users"]
```

## Complete Example

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
    async def create_todo(self, todo: TodoCreate):
        created = await self.store.create(todo.model_dump())
        return created, 201

    @router.put("/{todo_id}", summary="Update todo", request_model=TodoCreate, response_model=TodoResponse)
    async def update_todo(self, todo_id: int, todo: TodoCreate):
        updated = await self.store.update(todo_id, todo.model_dump())
        return updated if updated else ({"error": "Not found"}, 404)

    @router.delete("/{todo_id}", summary="Delete todo")
    async def delete_todo(self, todo_id: int):
        await self.store.delete(todo_id)
        return {"message": "Todo deleted"}

@module(services=[DataStore, Todos])
class App(ModuleBase):
    pass

if __name__ == "__main__":
    import uvicorn

    app = App()
    app.init()
    uvicorn.run(app, lifespan="on")
```

`Todos` declares an explicit `prefix="/todos"`, so its routes are served at `/todos`, `/todos/{todo_id}`, etc. `DataStore` has no `Router`, so it contributes no routes — it's a plain injected dependency. See [Services](./services.md) and [Modules](./modules.md) for the broader composition model.

## Best Practices

1. **Route Organization** — organize routes by feature (users, posts, todos) using separate service classes, each with its own `Router` attribute and an explicit `prefix`.
2. **Explicit Prefixes** — always set `Router(prefix=...)` on services composed into a module; relying on a no-prefix router across multiple services risks path collisions (`ValueError` at assembly).
3. **Query Params in the Path** — remember that a defaulted parameter only binds from the query string if it's declared in the route's path string (`?key={key}`).
4. **Parameter Validation** — use Pydantic models for request bodies; let auto-detection or explicit `request_model` handle parsing and validation.
5. **Error Handling** — return `(data, status_code)` tuples for non-2xx responses, and use `response_model` for accurate OpenAPI schema documentation (it does not affect runtime behavior).
6. **Documentation** — add `summary` and `description` to each route for clearer auto-generated OpenAPI docs.
7. **Tag Grouping** — use tags at both router and method level for clear API grouping.
