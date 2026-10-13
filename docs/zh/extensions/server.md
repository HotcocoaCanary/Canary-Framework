# Web 服务器

`canary_framework.web.asgi.server` 的 `Server` 是一个监听端口的单元：监听是它的 `@start`，
关闭是它的 `@stop`。它站在 ASGI 协议的服务器一侧，服务**任何** ASGI 应用——本框架的
[应用单元](app.md)、一个 FastAPI 对象、手写的 `async def app(scope, receive, send)`。

```bash
pip install "canary-framework[server]"
```

!!! note "暂行 API"
    扩展包在稳定之前可能在次版本中调整，见[版本与兼容性](../versioning.md#extensions)。

## 依赖即服务

```python
from canary_framework import dep
from canary_framework.web.asgi.server import Server


class Gateway(Server):
    api = dep(LibraryApi)           # 一个应用单元，应答 /
    metrics = dep(Metrics)          # 另一个，应答 /metrics

    host = "0.0.0.0"
    port = 8010


async with Gateway():
    ...
```

`Server` 直接依赖的单元里，**可调用并且声明了 `path`** 的就是应用，各自在它的端口上应答
自己的 `path`。两个条件缺一不可：数据库、配置不可调用；一个恰好写了 `__call__` 的策略对象
没有 `path`——它们都只是普通依赖。

| 阶段 | `Server` 做的事 |
|---|---|
| `@start` | 绑定端口并开始服务。它依赖的单元此时都已启动 |
| `@stop` | 停止接收新连接，等在途请求结束 |

应用是被依赖的一方，所以它们的 `@start` 先于监听、`@stop` 晚于关闭——数据库也一样。这就是
依赖顺序，不需要另外安排。

- 端口被占用时 `start()` 抛出 `OSError`，已启动的依赖照常回收。
- `port = 0` 由系统分配端口。服务期间 `server.port` 是实际端口，停止后还原成 0，所以重启会
  重新分配。
- 两个应用的 `path` 相同时，`start()` 抛出 `LifecycleError`。
- 同一个应用单元可以被两个 `Server` 依赖，例如对外一个端口、对内一个端口；它仍然只有一个
  实例。

## 手写的应用单元

一个可调用、声明了 `path` 的单元就是应用单元，不需要继承什么：

```python
class Metrics(Canary):
    registry = dep(Registry)

    path = "/metrics"

    async def __call__(self, scope, receive, send) -> None:
        await self.registry.asgi_app(scope, receive, send)
```

## 别的框架的应用

在 `@init` 里给 `self.app` 赋任何一个 ASGI 应用。赋了值就以它为准，依赖的应用单元不再自动
加入：

```python
fastapi_app = FastAPI()


class Gateway(Server):
    port = 8010

    @init
    def build(self) -> None:
        self.app = fastapi_app
```

### 应用自己的 lifespan

`Server` 默认不向应用发 ASGI 的 lifespan 消息：启动与回收归 Canary 的生命周期。这对"先只换
服务器"的迁移是个坑——老应用写在 `lifespan` / `on_event("startup")` 里的连接池、缓存预热会
**悄悄不执行**，而接口照样能通。两种处理：

- 用类参数打开：`class Gateway(Server, lifespan="on")`。应用的启动发生在 `Server` 的 `@start`
  里、监听之前，回收发生在 `@stop` 里；应用启动失败就是 `Server` 启动失败，已启动的依赖
  照常回收。本框架的应用单元此时已由 Canary 启动，只会应答，不会被重复驱动。
  它只对赋给 `self.app` 的那个应用生效：[`dispatch`](#dispatch) 对 lifespan 只应答、不转发，
  经它拼进去的应用收不到这些消息。
- 或者把那部分搬成一个单元的 `@start` / `@stop`，让 `Server` 依赖它——迁移的终点通常是这个。

### 在别的框架的接口里用单元

别的框架的接口是模块级函数，不是单元的方法，依赖没法写成 `dep()`，要在请求时去图上取。
以 FastAPI 为例，这座桥十来行：

```python
from canary_framework import Canary
from canary_framework.test import unit
from fastapi import Depends, FastAPI, Request


def attach(app: FastAPI, root: Canary) -> None:
    app.state.graph = root          # 在 Server 的 @init 里调用：attach(fastapi_app, self)


def use[T: Canary](cls: type[T]) -> T:
    async def resolve(request: Request) -> T:       # 必须是 async def
        return unit(request.app.state.graph, cls)

    return Depends(resolve)


@fastapi_app.get("/readers/{reader_id}")
async def show(reader_id: int, readers: ReaderService = use(ReaderService)) -> Reader:
    return await readers.get(reader_id)
```

两点：

- **依赖函数写成 `async def`。** FastAPI 会把同步的依赖函数放进线程池，每个请求多一次线程
  切换；这里只是查一次字典，实测写成同步的会让吞吐掉到三分之一。
- **按类型取单元用 `canary_framework.test.unit`。** 它虽然放在 `test` 包里，做的就是"从一张
  图上按类型取回单元"这一件事，生产代码里用它没有问题。

## 路径怎么分发 { #dispatch }

请求按**最长前缀**交给应用，前缀按整段匹配：`/api` 应答 `/api` 与 `/api/...`，不应答
`/apix`；`/` 应答其余一切。没有匹配时 HTTP 得到 404。

只转发，不改写：应用看到的仍是完整路径，所以应用自己的路由要包含这个前缀。这不是 Starlette
意义上的"挂载"。

自动拼装用的是 `canary_framework.web.asgi.dispatch`，需要手动拼时直接用它：

```python
from canary_framework.web.asgi import dispatch


class Gateway(Server):
    api = dep(LibraryApi)
    port = 8010

    @init
    def build(self) -> None:
        self.app = dispatch({"/legacy": legacy_app, "/": self.api})
```

## uvicorn 的配置

`Server` 内部用 uvicorn。类参数原样传给 `uvicorn.Config`，子类继承父类的类参数，只覆盖自己
写出的那些：

```python
class Gateway(Server, timeout_graceful_shutdown=10, proxy_headers=True):
    api = dep(LibraryApi)
```

`timeout_graceful_shutdown` 值得设。不设时 `@stop` 会一直等到在途请求全部结束：一个不结束
的长连接就能让停机卡住，排在它后面的数据库等依赖也得不到回收，进程最后被强行杀掉。

地址用 `host` / `port` 类属性。`app`、`host`、`port`、`uds`、`fd`、`reload`、`workers` 在这里
另有归属，不能作为类参数，传了会在定义类时抛出 `TypeError`。`lifespan` 默认是 `"off"`，见上文。

WebSocket 需要另装一个实现（`websockets` 或 `wsproto`），uvicorn 本身不带。

## 进程归 Canary

生命周期由 Canary 驱动，因此：

- 服务器不接管信号，何时退出由进程入口决定；
- 没有 `--reload` 与 `--workers`。需要它们时不用 `Server`，把[应用单元](app.md)直接交给
  uvicorn。

响应信号的入口：

```python
async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    async with Gateway():
        await stop.wait()
```

`Server` 不必是根单元。守护进程顺带开一个管理端口，就是根上多一条 `dep(AdminServer)`。

## 测试

```python
class TestGateway(Gateway):
    port = 0


async with running(TestGateway) as gateway, httpx.AsyncClient() as client:
    response = await client.get(f"http://127.0.0.1:{gateway.port}/api/readers/7")
```
