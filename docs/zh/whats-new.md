# 1.2 新特性

1.2 在核心旁边增加了四个扩展包。核心只有两处修正，第一处会改变一种写法的结果，放在最前面。
其余代码不需要改动。

更早版本的变化见 [1.1 新特性](whats-new-1.1.md) 与 [1.0 新特性](whats-new-1.0.md)。

## 行为修正：子类同名覆盖一条依赖是替换

依赖现在和钩子一样按属性名解析。子类用同名属性再写一条 `dep()`，基类那条就被替换：

```python
class Service(Canary):
    store = dep(SqlStore)


class TestService(Service):
    store = dep(MemoryStore)    # 1.1：SqlStore 仍被构造并启动。1.2：只有 MemoryStore。
```

用同名的非 `dep()` 值覆盖，这条依赖就被去掉。如果你的代码依赖旧行为——指望基类那条依赖在
子类里仍然启动——给它另起一个属性名。

## 扩展包

四个扩展包与核心一起发布、共用一个版本号。核心不 import 它们，`import canary_framework` 依旧
不带入任何第三方包；用到哪个装哪个。

| 包 | 内容 | 安装 |
|---|---|---|
| [`canary_framework.test`](extensions/test.md) | 带替身启动一张图，按类型取回单元 | 随核心 |
| [`canary_framework.config`](extensions/config.md) | 同时是单元的 pydantic-settings 配置 | `canary-framework[config]` |
| [`canary_framework.web.asgi.app`](extensions/app.md) | 应用单元：一个小型 Web 框架 | `canary-framework[app]` |
| [`canary_framework.web.asgi.server`](extensions/server.md) | 服务器单元：监听是生命周期的一部分 | `canary-framework[server]` |

`canary-framework[web]` 同时安装应用与服务器两侧。

它们目前是**暂行**的：在各自被宣布稳定之前，API 可能在次版本中调整，见
[版本与兼容性](versioning.md#extensions)。

### 一个例子

```python
from canary_framework import dep
from canary_framework.config import Settings
from canary_framework.test import running
from canary_framework.web.asgi.app import App, Router, get
from canary_framework.web.asgi.server import Server


class AppConfig(Settings):
    greeting: str = "hello"


class ReaderApi(Router, prefix="/readers"):
    config = dep(AppConfig)

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return Reader(id=reader_id, name=self.config.greeting)


class LibraryApi(App):
    readers = dep(ReaderApi)


class Gateway(Server):
    api = dep(LibraryApi)
    port = 8010


async with Gateway():                   # 绑定端口是 @start，关闭是 @stop
    ...

async with running(Gateway, {AppConfig: AppConfig(greeting="hi")}) as gateway:
    ...                                 # 测试：换一份配置启动整张图
```

路由和应用都是单元，依赖走 `dep()`。应用单元自己就是一个 ASGI 应用，所以也可以不用 `Server`，
直接 `uvicorn main:app`；反过来，`Server` 也能服务任何 ASGI 应用，包括一个 FastAPI 对象。

应用单元不生成 OpenAPI，但 `App.endpoints` 公开了拍平之后的接口表，照着它写一份只要几十行，
见 [Web 应用 › 接口表](extensions/app.md#endpoints)。

## 1.2 还有

- `Scope.entered(phase)` 始终按"依赖在前"返回。此前对只 `init` 过、从未启动的图调用 `stop()`
  之后再 `start()`，顺序会变成根在前。
- [常见用法](patterns.md)新增两节：[同一种东西的多个实例](patterns.md#several-instances-of-one-kind)
  与[分两步停机](patterns.md#two-step-shutdown)。
- `benchmarks/web.py`：同一组接口分别写成应用单元与 FastAPI，逐个场景压测。
- 开发环境：`dev` extra 现在包含扩展包的依赖，新增只含核心测试所需的 `test`；CI 另在没有这些
  依赖的环境里跑核心测试。
- 完整清单见
  [变更日志](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md)。
