# ASGI

`canary_framework.asgi` 把"应用"和"监听"分成两种单元：

- **`App`** 是应用单元：一个 ASGI 应用，自己不监听。[`asgi.fastapi`](fastapi.md) 的 `App` 就是一个。
- **`Server`** 是监听的单元：每个端口一个，服务它直接依赖的应用单元。

应用是值，可以有很多个；需要唯一的是端口。所以一个进程里放几个服务，都只有一个监听器。

```bash
pip install "canary-framework[asgi]"
```

!!! note "暂行 API"
    扩展包在稳定之前可能在次版本中调整，见[版本与兼容性](../versioning.md#extensions)。

## 一个端口，多个应用

```python
from canary_framework import asgi, dep


class Gateway(asgi.Server):
    api = dep(LibraryApi)           # 一个 FastAPI 应用单元，应答 /
    metrics = dep(Metrics)          # 另一个应用单元，应答 /metrics

    host = "0.0.0.0"
    port = 8010


async with Gateway():
    ...
```

**依赖即服务**：`Server` 直接依赖的应用单元都在它的端口上，各自应答自己的 `path`。这和路由
单元是同一条规则。

| 阶段 | `Server` 做的事 |
|---|---|
| `@start` | 绑定端口并开始服务。它依赖的单元此时都已启动 |
| `@stop` | 停止接收新连接，等在途请求结束 |

应用是被依赖的一方，所以它们的 `@start` 先于监听、`@stop` 晚于关闭——数据库也一样。这就是
依赖顺序，不需要另外安排。

端口被占用时 `start()` 抛出 `OSError`，已启动的依赖照常回收。`port = 0` 由系统分配端口，
开始服务后 `server.port` 是实际端口。两个应用的 `path` 相同时，`start()` 抛出
`LifecycleError`。

同一个应用单元可以被两个 `Server` 依赖，例如对外一个端口、对内一个端口；它仍然只有一个实例。

## 路径怎么分发

请求按**最长前缀**交给应用，前缀按整段匹配：`/api` 应答 `/api` 与 `/api/...`，不应答
`/apix`；`/` 应答其余一切。没有匹配时 HTTP 得到 404。

只转发，不改写：应用看到的仍是完整路径，所以应用自己的路由要包含这个前缀。这不是 Starlette
意义上的"挂载"。

## 自己的应用单元

任何 ASGI 应用都可以是应用单元，在 `@init` 里赋给 `self.app`：

```python
class Metrics(asgi.App):
    registry = dep(Registry)

    path = "/metrics"

    @init
    def build(self) -> None:
        self.app = make_asgi_app(self.registry)
```

## 手动拼装

在 `Server` 的 `@init` 里给 `self.app` 赋值，就以它为准，依赖的应用单元不再自动加入。
`dispatch` 是自动拼装用的同一个函数：

```python
class Gateway(asgi.Server):
    api = dep(LibraryApi)
    port = 8010

    @init
    def build(self) -> None:
        self.app = asgi.dispatch({"/legacy": legacy_wsgi_bridge, "/": self.api.app})
```

## 进程归 Canary

生命周期由 Canary 驱动，因此：

- ASGI 的 lifespan 是关闭的。应用需要的启动与回收，写成应用单元的 `@start` / `@stop`；
- 服务器不接管信号，何时退出由进程入口决定；
- 没有 `uvicorn main:app`，也就没有 `--reload` 与 `--workers`。多进程交给容器副本或进程
  管理器。

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
