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

- **`prefix`**（str，默认 `""`）— 应用于此 Router 上所有已注册路由的 URL 前缀。它与每条路由自身的路径拼接，构成最终服务的路径（见[挂载 Router](#mount-router)）。
- **`tags`**（`list[str]`，仅关键字）— 自动应用于该 Router 上所有端点的 OpenAPI 标签。

!!! tip
    `Router` 本身并不知道 service 或 module 的存在 —— 它只是累积 `RouteInfo` 条目。当路由被组装时，service 的 `router` 属性会被发现并绑定到 `self`（见[挂载 Router](#mount-router)）。

## HTTP 方法装饰器

`Router` 实例提供五个 HTTP 方法装饰器：`.get()`、`.post()`、`.put()`、`.delete()`、`.patch()`。

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

路由处理器**不**接收 `request` 参数。参数按**名称**绑定：路径参数、查询参数与请求体。

## 路径参数

路由模式中的路径参数会自动绑定到同名的函数参数：

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

框架会将字符串路径段转换为参数声明的类型（`int`、`float`、`str`、`bool`，以及这些类型的 `Optional[T]`）。无法转换的值返回 **400**。

## 查询参数

!!! warning "查询参数必须在路径字符串中声明"
    与路径参数不同，一个函数参数不会因为带有默认值就被当作查询参数。它还必须通过 `?key={key}` 语法出现在路由的路径字符串中。一个带默认值但**未**在路径字符串中声明的参数，只会保留其默认值 —— 它永远不会从查询字符串中读取。

```python
@service()
class Search(ServiceBase):
    router = Router(prefix="/search")

    # q、page、limit 都在路径字符串中声明，因此会从查询字符串绑定。
    # 其他任何参数都只会保留默认值。
    @router.get("/?q={q}&page={page}&limit={limit}")
    async def search(self, q: str = "", page: int = 1, limit: int = 10):
        return {"query": q, "page": page, "limit": limit}
```

请求 `/search?q=canary&page=2&limit=5` 绑定 `q="canary"`、`page=2`、`limit=5`。请求中省略的参数保持其默认值。

```python
# 错误示例 —— `active` 带默认值，但未在路径字符串中声明，
# 因此永远不会从查询字符串绑定；它始终是 True。
@router.get("/users")
async def list_users(self, active: bool = True):
    ...

# 正确示例 —— 在路径中声明它，才能从 ?active=... 绑定
@router.get("/users?active={active}")
async def list_users(self, active: bool = True):
    ...
```

没有默认值的查询参数是必填的：缺失或无效的值返回 **422**。

## 请求体

处理器的**请求体参数**是第一个既非路径参数、也非查询参数（按路径字符串中的声明判断）的参数，它不必命名为 `body`。

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
        # `item` 被自动探测为 request_model（它是 BaseModel 子类，
        # 且既非路径参数也非查询参数）。
        return {"name": item.name, "price": item.price}, 201
```

`request_model` 会从第一个非路径/查询参数的 `BaseModel` 类型参数自动探测；你也可以显式传入：

```python
    @router.post("/", request_model=CreateItem)
    async def create(self, item: CreateItem):
        ...
```

当预期存在请求体时：

1. 请求体会被解析为 JSON —— 无效 JSON 返回 **400**。
2. 它会针对解析出的 `request_model` 进行校验 —— `ValidationError` 返回 **422**。
3. 校验通过的模型实例会传给请求体参数（使用它的实际名称，无论是什么）。

## 服务依赖

依赖通过类型注解声明 —— 无需 `deps` 列表：

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

完整的 DI 机制参见[依赖注入](./dependency-injection.md)。

## 挂载 Router {#mount-router}

!!! warning "行为变更：仅支持显式前缀（D4）"
    Canary 使用**显式前缀**模型。不存在 `/{ServiceName}` 自动命名空间 —— 没有 `prefix` 的 Router 会在裸路径上直接服务。如果你此前依赖隐式的按服务挂载，请为每个 Router 显式设置 `prefix=` 以还原原有的命名空间，例如 `Router(prefix="/users")`。

module 组合（compose）service，而不是把它们「挂载」到某个派生路径上。每条路由都服务于 `router.prefix + route_path`（重复的 `/` 会被折叠），无论其所属 service 是独立运行还是嵌套在 module 树中：

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

# 最终服务路径：
#   GET /users/{user_id}   （Users 自身的前缀）
#   GET /items/            （Items 自身的前缀）
```

module 也会递归收集嵌套 module 的路由 —— 整棵组合树被拉平成一张路由表，每个节点贡献自己已经拼好前缀的路径（父级不会再叠加额外前缀）。

如果树中任意两条路由解析出相同的 `(method, full_path)`，组装时会抛出 `ValueError` —— 这是一次真实的冲突检测，而非静默覆盖。

```python
@service()
class A(ServiceBase):
    router = Router()  # 无前缀

    @router.get("/ping")
    async def ping(self): ...

@service()
class B(ServiceBase):
    router = Router()  # 无前缀 —— 与 A 的 "/ping" 冲突

    @router.get("/ping")
    async def ping(self): ...

@module(services=[A, B])
class App(ModuleBase):
    pass

# app.init() 后访问 asgi_app 会抛出：
#   ValueError: Route collision: GET /ping
```

!!! note "独立运行与由 module 装配的行为一致"
    直接运行的单个 `@service`（`app = MyService(); app.init(); uvicorn.run(app, ...)`）与被组合进 module 的同一 service，会服务于相同的路径 —— 唯一的区别是被组装的子树范围不同。参见 `examples/01_standalone.py` 与 `examples/04_module_router.py` 的对比。

## 根路由

文档端点 —— Swagger UI、ReDoc 与 OpenAPI JSON schema —— 只会在你实际运行的节点（「运行节点」）上生成**一次**：即你调用 `.init()` 并作为 ASGI 应用来 serve 的那个 `ServiceBase`/`ModuleBase` 实例。组装过程会遍历该节点下的整棵子树，收集所有路由、检测冲突，并构建一张 Starlette 路由表 + 一份 OpenAPI 文档，暴露：

- **`GET /docs`** — Swagger UI
- **`GET /redoc`** — ReDoc
- **`GET /openapi.json`** — OpenAPI 3.0.3 schema

这些路径（以及 Swagger/ReDoc 的 CDN URL）可通过 `CanaryConfig` 配置 —— 参见[文档端点](./configuration.md#docs-endpoints)。文档默认开启，没有 `docs=True` 这样的开关。

组装是懒加载且记忆化的：首次访问 `asgi_app` 或 `openapi()` 会触发组装，结果会被缓存。`ModuleBase.init()` 会重置该缓存，因此 `init()` 之前的访问不会用不完整的树污染记忆化结果。

## OpenAPI 文档参数

HTTP 方法装饰器支持以下关键字参数（参见 `core/router/_base.py` 中的 `Router`）：

| 参数 | 类型 | 描述 |
|------|------|------|
| `summary` | `str \| None` | 操作的简短摘要 |
| `description` | `str \| None` | 操作的详细描述 |
| `request_model` | `type \| None` | 请求体的 Pydantic 模型（自动解析并校验） |
| `response_model` | `type \| None` | 仅用于 OpenAPI 响应 schema 的 Pydantic 模型 |
| `responses` | `dict \| None` | 自定义响应定义 |
| `tags` | `list[str] \| None` | API 分组标签（与 Router 自身的 tags 合并） |
| `deprecated` | `bool` | 此操作是否已弃用 |
| `operation_id` | `str \| None` | 唯一操作标识符 |

!!! note
    不存在 `path_params` / `query_params` 这两个关键字参数 —— 路径与查询参数的 schema 会根据路由的路径字符串和处理器的类型注解自动推导。

`response_model` 仅影响 OpenAPI 文档 —— 它**不会**校验或过滤处理器实际返回的响应内容。

## 状态码与类型转换

| 情况 | 状态码 |
|------|--------|
| 路径参数无效（类型转换失败） | **400** |
| 缺少必填查询参数，或查询值无效 | **422** |
| 请求体无效 / 非 JSON | **400** |
| 请求体未通过 `request_model` 校验 | **422** |

路径/查询参数的类型转换（`_convert_param`）：`int`、`float`、`str` 直接转换；`Optional[T]` 会先被解包。对于 `bool`，字符串会被转小写并匹配：

- `1`、`true`、`yes`、`on` → `True`
- `0`、`false`、`no`、`off` → `False`
- 其他任何值 → 转换出错 → **422**（查询参数）/ **400**（路径参数）

## 返回值

处理器可以返回多种形式；`_auto_response` 负责转换：

=== "dict / list"
    ```python
    @router.get("/items")
    async def list_items(self):
        return {"items": [1, 2, 3]}  # → JSONResponse
    ```

=== "Pydantic 模型"
    ```python
    @router.get("/items/{item_id}")
    async def get_item(self, item_id: int):
        return ItemModel(id=item_id, name="widget")  # → JSONResponse(model_dump())
    ```

=== "(body, status_code) 元组"
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
        return RedirectResponse("/new")  # → 原样返回
    ```

- `Response` 实例原样返回。
- 二元组 `(body, status_code)`，其中 `status_code` 是 `int`（且不是 `bool`）会设置 HTTP 状态码；`body` 的转换方式与顶层返回值相同（`Response`、`BaseModel`、`dict`/`list`、`str`，否则转为字符串）。
- 元组第二个位置的 `bool` **不会**被当作状态码 —— `(x, True)` 不是状态码元组，会走默认（字符串）转换路径。
- `dict`/`list`（包括其中嵌套的 `BaseModel`）→ `JSONResponse`。
- `BaseModel` → `JSONResponse(model_dump())`。
- `str` → `PlainTextResponse`。
- 其他任何类型 → `PlainTextResponse(str(result))`。

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

`Todos` 声明了显式的 `prefix="/todos"`，因此它的路由服务于 `/todos`、`/todos/{todo_id}` 等路径。`DataStore` 没有 `Router`，因此不贡献任何路由 —— 它只是一个被注入的普通依赖。更完整的组合模型参见[服务](./services.md)与[模块](./modules.md)。

## 最佳实践

1. **路由组织**：按功能（users、posts、todos）组织路由，使用独立的 service 类，各自拥有 `Router` 属性和显式的 `prefix`。
2. **显式前缀**：为组合进 module 的 service 始终设置 `Router(prefix=...)`；多个 service 都使用无前缀 Router 存在路径冲突风险（组装时抛出 `ValueError`）。
3. **查询参数需在路径中声明**：记住带默认值的参数只有在路由路径字符串中声明（`?key={key}`）后，才会从查询字符串绑定。
4. **参数校验**：为请求体使用 Pydantic 模型，交由自动探测或显式 `request_model` 处理解析与校验。
5. **错误处理**：对非 2xx 响应返回 `(data, status_code)` 元组，并使用 `response_model` 获得准确的 OpenAPI schema 文档（它不影响运行时行为）。
6. **文档**：为每个路由添加 `summary` 和 `description`，让自动生成的 OpenAPI 文档更清晰。
7. **标签分组**：在 Router 级别和方法级别使用 tags，以获得清晰的 API 分组。
