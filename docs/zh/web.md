# Web 应用

`canary_framework.web` 把 `@cocoa` 服务直接暴露为 ASGI web 应用。它基于 **Starlette** 做
路由/请求，基于 **Pydantic v2** 做校验与文档，同时沿用 `@cocoa` + `Canary` 的同一套生命
周期。

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


@web_cocoa(deps=[BookRepository, LibraryService], prefix="/api", tags=["library"])
class LibraryAPI:
    @get("/books/{book_id}")                       # 命中占位符 → 路径参数
    async def get_book(self, book_id: int) -> dict:
        return self.book_repository.get(book_id)

    @get("/books")                                 # 标量 → 查询参数
    async def search(self, q: str = "") -> list[dict]:
        return self.book_repository.search(q)

    @post("/books/{book_id}/borrow", status_code=201)   # 模型 → 请求体
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict:
        return {"result": self.library_service.borrow(body.member_id, book_id)}


app = Canary(LibraryAPI)  # `app` 本身就是 ASGI 应用
```

运行：

```bash
uvicorn examples.library.web:app --reload
```

打开 `/docs`（Swagger UI）或 `/openapi.json` 查看自动生成的文档。

**handler 必须是 `async def`。** 同步函数会在事件循环线程上运行，阻塞的不是它自己那个
请求，而是整个进程 —— 框架不替你偷偷挪进线程池（那会让"这段代码跑在哪儿"变成隐式的），
而是在装配期直接拒绝。有阻塞调用就显式让出：`await asyncio.to_thread(blocking_call, ...)`。

## 参数从哪来

推断规则只有一句：**标量走查询串（名字命中路径占位符则走路径），其余走请求体。**

| 来源 | 规则 |
|---|---|
| **path** | 参数名命中路由路径里的 `{param}`（如 `/books/{book_id}`） |
| **query** | 其它标量 —— 能从一个字符串无歧义还原的类型，以及它们的 `list` / `Union` |
| **body** | 其余一切：Pydantic 模型、`dict`、`list[Model]` …… |
| **request** | 注解是 `starlette.requests.Request` → 注入原始请求对象 |
| **header / cookie** | 只能显式声明，见下 |

标量值用 Pydantic 做类型转换，所以 `book_id: int` 拿到的是 `int`，尽管 URL 里是字符串。

### 请求头与 Cookie

只有这两处推断够不着 —— `x: str` 看不出想读的是 `X-Token` 还是 `?x=`，所以必须显式说：

```python
from typing import Annotated
from canary_framework.web import Cookie, Header, get


@get("/whoami")
async def whoami(
    self,
    x_token: Annotated[str, Header()] = "anonymous",
    session: Annotated[str, Cookie(alias="sid")] = "",
) -> dict: ...
```

请求头名会自动把下划线换成连字符（`x_token` → `x-token`）；`alias` 用于协议名和形参名
对不上的时候。`Header` / `Cookie` 还接受 `description=`，会进 OpenAPI 文档。

**标记只能写在 `Annotated` 里**，默认值就写在默认值该在的位置。写成 `x_token: str =
Header()` 会在装配期被拒绝 —— 那让"默认值"这个位置同时表示两件事。

没有 `Query` / `Path` / `Body` 标记：推断规则已经给出同样的答案，再写一遍只是重复。

### 校验约束

`Annotated` 里的 Pydantic 元数据会被完整保留 —— 既参与校验，也进 OpenAPI 文档：

```python
from pydantic import Field


@get("/items")
async def items(self, page: Annotated[int, Field(gt=0, le=100)] = 1) -> dict: ...
```

`?page=-5` 得到 422，文档里的 schema 也带上了 `exclusiveMinimum: 0`。

### 请求体

一个请求只有一个请求体，所以**一个 handler 只能有一个请求体形参** —— 写两个会在装配期
报错，框架不做按形参名自动嵌套那种隐式行为。

请求体形参给了默认值就是**可选请求体**：

```python
@post("/items")
async def create(self, item: Item | None = None) -> dict:
    return {"got": item is not None}
```

## 响应

返回 `dict`、`list` 或 Pydantic 模型。**返回值会先按返回注解校验、再序列化为 JSON**：

```python
@get("/books/{book_id}")
async def get_book(self, book_id: int) -> Book: ...
```

`/docs` 照着这个注解向调用方承诺了响应的形状，所以框架会当真：返回的东西不符合声明是
**服务端的 bug**，走 500 并把细节留在服务器日志里，而不是悄悄发出去。

### 状态码

```python
@post("/books", status_code=201)
async def create(self, body: NewBook) -> Book: ...


@delete("/books/{book_id}", status_code=204)
async def remove(self, book_id: int) -> None: ...
```

`204` / `304` 按 HTTP 规范不能带响应体，框架发一个空响应。

需要按情况变化的状态码时，自己造一个 `Response` 返回 —— 它自己的状态码说了算：

```python
from starlette.responses import JSONResponse, StreamingResponse


@get("/export")
async def export(self) -> StreamingResponse:      # SSE、文件下载、后台任务都走这里
    return StreamingResponse(rows())
```

## 错误怎么变成响应

异常只有三条固定出路，全部由框架内置，不需要也不能登记：

| 情况 | 结果 |
|---|---|
| 请求绑不上签名（缺参、请求体不是 JSON、字段校验失败） | **422**，`{"detail": ...}` |
| `raise HTTPError(status, detail)` | 它自带的状态码 |
| 其余任何异常 | **500**，`{"detail": "Internal Server Error"}`，traceback 照常进服务器日志 |

`HTTPError` 是从代码深处产生一个 4xx / 5xx 的唯一途径 —— 请求本身就不该成立时（没权限、
没登录、资源真的不存在）用它：

```python
from canary_framework.web import HTTPError


@get("/books/{book_id}")
async def get_book(self, book_id: int) -> Book:
    book = self.repo.find(book_id)
    if book is None:
        raise HTTPError(404, "no such book")
    return book
```

**业务上"预期内的失败"不要用异常表达。** 那种失败该由 handler 以返回值表达 —— 比如统一
响应体里的 `code` 字段。框架不参与业务语义，只管"请求根本没成立"和"服务端炸了"这两件事。

领域异常不该继承 `HTTPError`：那会让领域层知道 HTTP 的存在。在 handler 里把它翻译成返回
值或 `HTTPError`。

## 前缀

`@web_cocoa(prefix="/api")` 给该单元的所有路由加上公共前缀。

**前缀是绝对的**，与这个单元被谁依赖无关：

```python
@web_cocoa(prefix="/admin")
class AdminRouter:
    @get("/dashboard")
    async def dashboard(self) -> dict: ...


@web_cocoa(prefix="/api", deps=[AdminRouter])
class ApiRouter:
    @get("/users")
    async def users(self) -> list[dict]: ...
```

```text
GET /api/users            → ApiRouter.users
GET /admin/dashboard      → AdminRouter.dashboard     ← 不是 /api/admin/dashboard
```

依赖关系说的是启动顺序和谁能调用谁，URL 说的是对外的资源命名 —— 两件事，不该互相决定。
想要 `/api/admin` 就直接写 `prefix="/api/admin"`。

前缀会被归一化：`"api"`、`"/api/"`、`" api "` 都得到 `/api`。

## 文档

所有 `@web_cocoa` 单元的路由合并进同一个应用，`/openapi.json` 与 `/docs` 只有一份；
`title` 与 `version` 取最外层（离根最近）的那个单元。两条路由拼出同一个 `METHOD + 路径`
时，启动阶段抛 `RouteRegistrationError`。

文档元数据都是纯声明，运行时零影响：

```python
@web_cocoa(prefix="/api", tags=["library"], title="Library API", version="1.0.0")
class LibraryAPI:
    @get("/books", tags=["read"], summary="列出全部藏书")
    async def list_books(self) -> list[Book]:
        """更长的说明直接写 docstring —— 它就是 OpenAPI 里的 description。"""

    @get("/legacy", deprecated=True)
    async def legacy(self) -> dict: ...
```

`tags` 在两级上都能写：单元级的是公共标签，路由级的拼在它后面（上例 `/api/books` 的
tags 是 `["library", "read"]`）。`summary` 不给就用方法名。

## 路由必须挂在 web 单元上

`@get` 只有写在 `@web_cocoa` 单元上才会被收集。写在普通 `@cocoa` 上会在装配期抛
`DeclarationError` —— 从前这种写法是静默失效的（装饰器打上了、不报错、路由也不见了）。

## 生命周期

`Canary` 对 web 应用同样走显式的 `init()` / `start()` / `stop()`。在 uvicorn 下，ASGI
lifespan 会在启动时驱动 `init()` + `start()`、关闭时驱动 `stop()`。`@web_cocoa` 只是在
`@cocoa` 之上叠加了一个路由标记，依赖注入与钩子行为完全一致。

签名在**装配期**就被编译成一份取值计划（每个形参从哪来、用哪个校验器、返回值怎么序列化），
请求路径上因此没有任何反射 —— 不重算类型注解、不重建 `TypeAdapter`。分发与文档读的是同一
份计划，所以文档描述的绑定行为和实际行为不可能不一致。

## 测试

可选的 `test` 额外依赖会带上 `httpx2` —— Starlette 1.x 的 `TestClient` 底层使用它：

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
    with TestClient(Canary(LibraryAPI)) as client:   # with 会走 lifespan
        assert client.get("/books").json() == []
```

## 参考

| 名称 | 用途 |
|---|---|
| `@web_cocoa(deps=[...], prefix="", tags=(), title=..., version=...)` | 把类标记为路由持有者（`@cocoa` + web 标记）；`prefix` 是绝对前缀 |
| `@get` / `@post` / `@put` / `@patch` / `@delete` `(path, *, status_code=200, tags=(), summary=None, deprecated=False)` | 把方法标记为路由处理器 |
| `@route(method, path, ...)` | 上面五个的通用形式 |
| `Header(description=None, alias=None)` / `Cookie(...)` | 请求头 / cookie 参数，写在 `Annotated` 里 |
| `HTTPError(status_code, detail=None, headers=None)` | 自带 HTTP 语义的错误 |
| `WebError` / `RouteRegistrationError` / `RequestValidationError` | web 扩展的错误类型 |

## 明确不做的事

这些每一样单独看都合理，加起来就是重写一遍 FastAPI —— 而这个框架的差异化在 DI 和生命
周期，不在 web：

per-request 依赖注入（`Depends`）· 路由嵌套（`include_router`）· 中间件体系 · WebSocket ·
表单与文件上传 · `response_model=` 参数（返回注解够用）· 多状态码文档（`responses={}`）

需要这些能力时，Starlette 本身就在你手上 —— 自己造 `Response` 返回，或者把 `Canary` 当
纯粹的 DI 与生命周期容器，路由交给别的框架。
