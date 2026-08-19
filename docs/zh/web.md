# Web 应用

`canary_framework.web` 把 `@cocoa` 服务直接暴露为 ASGI web 应用。它基于 **Starlette** 做
路由/请求，基于 **Pydantic v2** 做校验与文档，带来 FastAPI 级的开发体验，同时沿用
`@cocoa` + `Canary` 的同一套生命周期。

```bash
pip install "canary-framework[web]"
```

## 快速上手

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService])  # @cocoa + web 路由
class LibraryAPI:
    @get("/books/{book_id}")  # 路径参数，自动注入
    async def get_book(self, book_id: int) -> dict:
        return self.book_repository.get(book_id)

    @get("/books")  # 查询参数
    async def search(self, q: str = "") -> list[dict]:
        return self.book_repository.search(q)

    @post("/books/{book_id}/borrow")  # Pydantic 模型 = 请求体
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict:
        return {"result": self.library_service.borrow(body.member_id, book_id)}


app = Canary(LibraryAPI)  # `app` 本身就是 ASGI 应用
```

运行：

```bash
uvicorn examples.library.web:app --reload
```

打开 `/docs`（Swagger UI）、`/redoc` 或 `/openapi.json` 查看自动生成的文档。

## 参数如何注入

每个 handler 参数（`self` 之后）按名从请求中绑定：

| 来源 | 规则 |
|---|---|
| **path** | 参数名命中路由路径里的 `{param}`（如 `/books/{book_id}`） |
| **query** | 其它标量，从查询串读取（`?q=...`） |
| **body** | 注解是 Pydantic `BaseModel` 子类 → 解析 JSON 请求体 |
| **request** | 注解是 `starlette.requests.Request` → 注入原始请求 |
| **header / cookie** | 显式的 `Header(...)` / `Cookie(...)` 标记 |

标量值用 Pydantic（`TypeAdapter`）做类型转换，所以 `book_id: int` 拿到的是 `int`，尽管
URL 里是字符串。缺少必填参数或请求体校验失败时映射为 **HTTP 422**。

用 `Query` / `Path` / `Header` / `Cookie` / `Body` 标记（作为默认值或经 `Annotated`）来
显式指定来源与元数据：

```python
from typing import Annotated
from canary_framework.web import get, Query, Header


@get("/items")
async def items(self, limit: Annotated[int, Query(default=10)]) -> list[int]: ...


@get("/whoami")
async def whoami(self, x_token: str = Header(default="")) -> dict: ...
```

Header 参数名会自动把下划线换成连字符（`x_token` → `x-token` 请求头）。

## 响应

返回 `dict`、`list` 或 Pydantic 模型。返回值会按返回注解校验后序列化为 JSON：

```python
@get("/books/{book_id}")
async def get_book(self, book_id: int) -> Book: ...
```

## 路由嵌套（`prefix`）

`@web_cocoa(prefix="/api")` 给该单元的所有路由加上公共前缀，而且**前缀沿依赖关系逐级
嵌套**——被依赖的 web 单元挂在依赖方的前缀之下：

```python
@web_cocoa(prefix="/admin")
class AdminRouter:
    @get("/dashboard")
    async def dashboard(self) -> dict: ...


@web_cocoa(prefix="/api", deps=[AdminRouter])
class ApiRouter:
    @get("/users")
    async def users(self) -> list[dict]: ...


app = Canary(ApiRouter)  # 只传根
```

```text
GET /api/users            → ApiRouter.users
GET /api/admin/dashboard  → AdminRouter.dashboard
```

链路中间的普通 `@cocoa`（非 web 单元）不贡献前缀，直接跳过：`Api -> Repo -> Admin` 与
`Api -> Admin` 挂载结果相同。

### 实例共享，挂载不共享

依赖图上每个类型依然只有一个实例，但**路由挂在依赖路径上**——同一个单元被两条路径依赖，
就在两个位置各挂一份，两处命中的是同一个对象：

```python
@web_cocoa(prefix="/c")
class C: ...


@web_cocoa(prefix="/b", deps=[C])
class B: ...


@web_cocoa(prefix="/a", deps=[B, C])
class A: ...
```

```text
/a          A
/a/b        B
/a/b/c      C   ┐ 同一个实例
/a/c        C   ┘ 两个挂载点
```

也就是说，服务身份（一个实例）和挂载位置（若干条路径）是分开的。两条路径拼出同一个前缀
时只挂一次，不会重复注册。

### 文档与冲突

所有 `@web_cocoa` 的路由合并进同一个应用，`/openapi.json` / `/docs` / `/redoc` 也只有一
份；`title` 与 `version` 取最外层（离根最近）的那个单元。若两条挂载路径拼出同一个
`METHOD + 路径`，启动时抛 `RouteRegistrationError`。

## 生命周期

`Canary` 对 web 应用同样走显式的 `init()` / `start()` / `stop()`。在 uvicorn 下，ASGI
lifespan 会在启动时驱动 `start()`、关闭时驱动 `stop()`；`@on_start` / `@on_stop` 钩子与
cocoa 依赖注入（`self.<dep>`）与核心引擎完全一致。`@web_cocoa` 只是在其上叠加了路由收集。

## 测试

可选的 `test` 额外依赖会带上 `httpx2`——Starlette 1.x 的 `TestClient` 底层使用它：

```bash
pip install "canary-framework[web,test]"
```

```python
from starlette.testclient import TestClient
from canary_framework import Canary
from canary_framework.web import get, web_cocoa


@web_cocoa
class LibraryAPI:
    @get("/books")
    async def list_books(self) -> list[dict]:
        return []


def test_list_books() -> None:
    with TestClient(Canary(LibraryAPI)) as client:
        assert client.get("/books").json() == []
```

## 参考

| 装饰器 / 类 | 用途 |
|---|---|
| `@web_cocoa(deps=[...], prefix=..., title=..., version=...)` | 把类标记为路由持有者（`@cocoa` + web 扩展）；`prefix` 沿依赖关系嵌套 |
| `@get(path)` / `@post(path)` / `@put(path)` / `@patch(path)` / `@delete(path)` / `@route(method, path)` | 把方法标记为路由处理器 |
| `Query` / `Path` / `Header` / `Cookie` / `Body` | 显式指定参数来源与元数据 |
| `Canary(*roots)` | ASGI 应用 / 编排器 |
| `uvicorn app:app` | 启动服务；ASGI lifespan 驱动 `init()` / `start()` / `stop()` |
