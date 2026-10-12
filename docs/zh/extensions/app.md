# Web

`canary_framework.asgi.web` 是一个小的 Web 框架，路由与应用都是单元，由
[`canary_framework.asgi`](asgi.md) 的服务器监听。它是 `asgi` 的子包，只依赖 pydantic。

```bash
pip install "canary-framework[web]"
```

它不提供依赖注入系统——依赖走 `dep()`——也不生成 OpenAPI。需要 OpenAPI 或 FastAPI 的生态时用
[`asgi.fastapi`](fastapi.md)；两个包并列，写法相近但不相同。

!!! note "暂行 API"
    扩展包在稳定之前可能在次版本中调整，见[版本与兼容性](../versioning.md#extensions)。

## 一个完整的例子

```python
import asyncio

from canary_framework import asgi, dep
from canary_framework.asgi.web import App, Request, Response, Router, error, get, post


class ReaderApi(Router, prefix="/readers"):
    readers = dep(ReaderService)

    @get
    async def search(self, keyword: str | None = None, limit: int = 20) -> list[Reader]:
        return await self.readers.search(keyword, limit)

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return await self.readers.get(reader_id)

    @post(status=201)
    async def create(self, body: NewReader) -> Reader:
        return await self.readers.create(body)


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)
    loans = dep(LoanApi)


class LibraryApi(App):
    api = dep(Api)

    @error(DomainError)
    async def on_domain_error(self, request: Request, exc: DomainError) -> Response:
        return Response.json({"msg": exc.message}, status=exc.code)


class Gateway(asgi.Server):
    library = dep(LibraryApi)
    port = 8010


async def main() -> None:
    async with Gateway():
        await asyncio.Event().wait()


asyncio.run(main())
```

## 路由

`Router` 是带前缀的单元，`get` / `post` / `put` / `patch` / `delete` 把它的方法标记为接口。
**聚合就是依赖**：`dep()` 一个路由单元，它就挂在自己之下，前缀逐层叠加。

- 路径省略时即所在单元的前缀本身：上例的 `@get` 对应 `GET /api/readers`。
- `{name}` 是路径参数，必须占一整段。
- 成功时的状态码写在标记上：`@post(status=201)`。
- 路由单元只有被 `App` 或另一个路由单元**直接**依赖时才会被挂载；被两处依赖则出现在两处
  前缀之下，背后是同一个实例。
- 接口方法是普通方法，测试里可以不经 HTTP 直接 `await api.show(3)`。

!!! warning "方法别叫 `get`"
    在类体里定义一个叫 `get` 的方法，会遮住它后面的 `@get`。给方法起别的名字。

### 匹配规则

应用在 `@init` 时把所有接口拍平成一张表：

- 不含参数的路径优先于含参数的：`/books/new` 先于 `/books/{book_id}`。
- 都含参数时，静态段靠左的优先：`/a/b/{y}` 先于 `/a/{x}/c`。
- 尾斜杠严格区分，不做重定向。
- `HEAD` 没有自己的接口时由 `GET` 应答。

## 形参怎么绑定

形参按以下顺序归类：

| 形参 | 来源 |
|---|---|
| 注解是 `Request` | 请求对象 |
| 名字出现在路径模板里 | 路径参数 |
| 名字是 `body` | JSON 请求体；注解为 `bytes` 时是原始字节 |
| 其余 | 查询参数 |

- 请求体**按名字**认：只有叫 `body` 的形参是请求体，所以一个接口最多一个。
- 查询参数有默认值即可选；注解是 `list[...]` 之类时取全部同名值（`?tag=1&tag=2`）。
- 没有注解的形参按 `str`。
- 校验与转换交给 pydantic，任何它能校验的类型都可以用。请求体用的是它的 JSON 模式：直接
  校验原始字节，所以 `strict=True` 的模型也接受 JSON 里的日期、UUID 这类字符串。
- 请求头与 Cookie 不做注解魔法，写一个 `request: Request` 自己读。

校验失败应答 422，一次报告全部出错的形参：

```json
{"detail": [{"loc": ["query", "limit"], "msg": "Input should be a valid integer, ...", "type": "int_parsing"}]}
```

## 同步与异步

- `async def` 的接口在事件循环里运行。
- 普通 `def` 的接口放进线程池（`asyncio.to_thread`），里面的阻塞调用——同步的数据库驱动、
  `requests`、文件读写——不会卡住别的请求。

`@error` 标记的处理器同样如此。两点要留意：`async def` 里的阻塞调用仍然会卡住整个进程；
线程池里的方法与事件循环并发运行，读写单元上的状态时要自己保证线程安全。

## 返回值与响应

| 返回 | 应答 |
|---|---|
| `Response` | 原样发出 |
| `None` | 空响应，204（标记上另写了 `status` 时用它） |
| 其余 | 按返回注解序列化成 JSON |

返回注解只用来序列化，不重新校验返回值。

`Response` 用来自己决定状态码、响应头与内容类型：

```python
return Response("pong")                                     # 纯文本
return Response.json({"id": 7}, status=201, headers={"location": "/readers/7"})
return Response(self.events(), media_type="text/event-stream")   # 异步迭代器：流式
```

## 异常

```python
raise HTTPError(404, "no such reader")
```

`HTTPError` 在接口、服务或任何被调用到的地方抛出都可以，应答 `{"detail": ...}`。路由不匹配
（404）、方法不允许（405，带 `Allow` 头）、校验失败（422）也是它。

`@error(异常类型)` 把应用单元的方法标记为处理器。异常交给类型最贴近的那个，返回值与接口的
返回值同样处理：

```python
class LibraryApi(App):
    @error(HTTPError)
    def envelope(self, request: Request, exc: HTTPError) -> Response:
        return Response.json({"code": exc.status, "msg": exc.detail}, status=exc.status)
```

没有处理器的异常应答 500 并记到 `canary_framework.asgi.web` 这个日志器，响应里不带内部细节。

## 中间件

`App` 的 `self.app` 就是一个 ASGI 应用。子类的 `@init` 在它建好之后运行，包一层即可，任何
ASGI 中间件都能用。本包不自带中间件——跨域（CORS）这类需求用现成的 ASGI 中间件，例如
Starlette 的 `CORSMiddleware`：

```python
class LibraryApi(App):
    api = dep(Api)

    @init
    def wrap(self) -> None:
        self.app = CORSMiddleware(self.app, allow_origins=["*"])
```

## 启动时就报错的事

以下问题在 `@init` 或定义类时抛出 `DeclarationError`，不会留到请求到来时：

- 同一个方法与路径有两个接口；
- 路径参数没有对应的形参；
- 看起来是请求体的形参（pydantic 模型、dataclass、`dict`）不叫 `body`；
- `*args` / `**kwargs`，或注解无法解析、无法校验；
- 前缀不以 `/` 开头，或以 `/` 结尾。

## 不做的事

OpenAPI、WebSocket、表单与文件上传、静态文件、后台任务。

## 测试

与其他单元一样用 [`running`](test.md)。不经网络：

```python
async with running(LibraryApi) as api:
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readers/7")
```

走真实的套接字：给 `Gateway` 的子类写 `port = 0`，见 [ASGI](asgi.md)。
