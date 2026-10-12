# FastAPI

`canary_framework.asgi.fastapi` 把 HTTP 表达成单元：路由是单元，FastAPI 应用也是单元，由
[`canary_framework.asgi`](asgi.md) 的服务器监听。它是 `asgi` 的子包，建在 `asgi` 之上。
参数解析、校验、序列化与 OpenAPI 都交给 [FastAPI](https://fastapi.tiangolo.com/)。

```bash
pip install "canary-framework[fastapi]"
```

!!! note "暂行 API"
    扩展包在稳定之前可能在次版本中调整，见[版本与兼容性](../versioning.md#extensions)。

## 一个完整的例子

```python
import asyncio

from canary_framework import Canary, asgi, dep
from canary_framework.asgi.fastapi import App, Router, get, post


class ReaderApi(Router, prefix="/readers", tags=["读者"]):
    readers = dep(ReaderService)

    @get("")
    async def search(self, keyword: str | None = None) -> list[Reader]:
        return await self.readers.search(keyword)

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return await self.readers.get(reader_id)

    @post("", status_code=201)
    async def create(self, body: NewReader) -> Reader:
        return await self.readers.create(body)


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)
    loans = dep(LoanApi)


class LibraryApi(App, title="图书馆 API", version="1.0.0"):
    api = dep(Api)


class Gateway(asgi.Server):
    library = dep(LibraryApi)

    host = "0.0.0.0"
    port = 8010


async def main() -> None:
    async with Gateway():
        await asyncio.Event().wait()


asyncio.run(main())
```

## 路由标记

`get` / `post` / `put` / `patch` / `delete` / `head` / `options` / `trace` / `api_route` /
`websocket` 就是 FastAPI `APIRouter` 的同名装饰器：名字、参数、默认值都一样，IDE 的补全和
FastAPI 的文档原样适用。区别只有一点——它们只把这次调用记在方法上，不改造方法；应用启动时
再原样重放到一个真正的 `APIRouter` 上，被装饰的是**绑定方法**。

- 你会的 FastAPI 写法都照旧：`response_model`、`status_code`、`dependencies`、`Depends`、
  `WebSocket` ……
- 路径必须写，和 FastAPI 一样。`""` 即所在路由单元的前缀本身：上例的 `@get("")` 对应
  `GET /api/readers`；应用单元自己的接口没有前缀，根路径写 `"/"`。
- 接口方法是绑定方法，单元之间的依赖直接用 `self` 上的 `dep()`；请求级的东西仍然可以用
  `Depends`。

与原生 FastAPI 的差别只有两处，也正是这个包存在的理由：接口是单元的方法，以及路由靠依赖
聚合而不是 `include_router`。想要一套不同的、更小的 Web 层，见 [`asgi.web`](web.md)。

!!! warning "方法别叫 `get`"
    在类体里定义一个叫 `get` 的方法，会遮住它后面的 `@get`。给方法起别的名字。

标记按**属性名**解析，与生命周期钩子一致：子类覆盖同名方法即替换；覆盖但不再标记时，它不再
是接口。

## 路由单元

`Router` 是一个带前缀与标签的单元。**聚合就是依赖**：`dep()` 一个路由单元，它就挂在自己
之下，前缀逐层叠加。路由树就是依赖图，没有单独的注册步骤。

它仍是普通单元：

- 有自己的依赖与钩子；
- 接口方法是普通方法，测试里可以不经 HTTP 直接 `await api.show(3)`；
- 它不是 FastAPI 的 `APIRouter`，方法与属性叫什么都不会与 FastAPI 冲突。

`prefix` 与 `tags` 之外的类参数原样传给 `APIRouter`。子类继承父类的类参数，只覆盖自己写出
的那些。

两条规则：

- 路由单元只有被 `App` 或另一个路由单元**直接**依赖时才会被挂载。
- 被两处依赖的路由单元出现在两处前缀之下，背后是同一个实例。

## 应用单元

`App` 是一个 [`asgi.App`](asgi.md)：它在 `@init` 里建出 FastAPI 应用 `self.app`，挂上自己
的接口与它直接依赖的路由单元。类参数原样传给 `FastAPI(...)`。

它自己不监听。哪个 `asgi.Server` 直接依赖它，它就在那个端口上；同一个端口上还可以有别的
应用单元。一个进程通常只需要一个 `App`，所以 OpenAPI 文档也只有一份。

### 配置应用

子类的 `@init` 在应用建好之后运行，此时还没有开始服务，中间件与异常处理器都来得及：

```python
class LibraryApi(App, title="图书馆 API"):
    api = dep(Api)

    @init
    def setup(self) -> None:
        self.app.add_exception_handler(DomainError, self.on_domain_error)

    async def on_domain_error(self, _: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"msg": str(error)}, status_code=400)
```

`self.app` 就是 FastAPI 应用，它的一切用法照旧。

### 已经有 FastAPI 应用时

只想要路由单元、应用和监听都沿用现有的，用 `mount`（同样从 `canary_framework.asgi.fastapi` 导入）把一张图上的路由挂上去：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Library() as root:       # Library 依赖若干 Router
        mount(root, app)
        yield


app = FastAPI(lifespan=lifespan)
```

生命周期归 Canary 而不是 uvicorn，入口怎么写、有哪些取舍，见 [ASGI](asgi.md)。

## 测试

用 `port = 0` 走真实的套接字：

```python
class TestGateway(Gateway):
    port = 0


async with running(TestGateway) as gateway, httpx.AsyncClient() as client:
    response = await client.get(f"http://127.0.0.1:{gateway.port}/api/readers/7")
```

或者不经网络、也不要任何服务器，直接请求应用单元：

```python
async with running(LibraryApi) as api:
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readers/7")
```

替换单元与其他测试一样，用 [`running`](test.md) 的第二个参数。
