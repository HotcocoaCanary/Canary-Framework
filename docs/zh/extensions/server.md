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

`Server` 直接依赖的单元里，凡是 ASGI 应用（可调用）的都在它的端口上，各自应答自己的 `path`
属性；没有 `path` 的应答 `/`。数据库、配置这类不可调用的依赖不受影响。

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

任何可调用的单元都是应用单元，不需要继承什么：

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

`Server` 不向应用发 ASGI 的 lifespan 消息：启动与回收归 Canary 的生命周期。别的框架的应用
若依赖自己的 lifespan，把那部分写成一个单元的 `@start` / `@stop`，让 `Server` 依赖它。

## 路径怎么分发

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

`host` / `port` 仍是类属性；`app`、`lifespan`、`reload`、`workers` 在这里另有归属，传了会在
定义类时抛出 `TypeError`。

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
