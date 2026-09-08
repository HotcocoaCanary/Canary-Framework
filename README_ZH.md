<h1 align="center">Canary Framework</h1>

<p align="center">
  一个极简、装饰器驱动的 <strong>依赖注入</strong>、<strong>生命周期</strong> 与
  <strong>ASGI Web 应用</strong> 框架 —— 纯 Python。
</p>

<p align="center">
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="PyPI" src="https://img.shields.io/pypi/v/canary-framework.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/canary-framework.svg"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/canary-framework.svg"></a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="https://hotcocoacanary.github.io/Canary-Framework/">中文文档</a> ·
  <a href="CHANGELOG.md">变更日志</a>
</p>

## 安装

```bash
pip install canary-framework            # 核心（零第三方依赖）
pip install "canary-framework[web]"     # + web 扩展（ASGI / OpenAPI）
```

需要 Python 3.12+。

## 核心模型

- **cocoa** 是最小运行单元 —— 一个被 `@cocoa` 标记的普通 Python class。依赖通过
  `deps=[...]` 声明；`@on_init` / `@on_start` / `@on_stop` 声明可选的生命周期行为。
- **Canary** 是编排器。`Canary(*roots)` 解析依赖图、拓扑排序、驱动完整生命周期 —— 它本身
  也是一个 ASGI 应用。

一条贯穿全框架的规则：

> **框架只造空壳，一切需要外界输入的事都在生命周期里做。**

单元一律由框架**无参构造**，所以 `__init__` 不能有必填参数 —— 需要什么就声明成依赖，值在
生命周期钩子里从协作者那里读。这样每一件需要输入的事都落在一个有台账、能逆序回收的阶段里。

## 快速开始

```python
import asyncio

from canary_framework import Canary, cocoa, on_init, on_start


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        print(f"准备连接 {self.config.database_url}")   # self.config 已注入

    @on_start
    async def connect(self) -> None: ...


@cocoa(deps=[Database])
class UserService: ...


async def main() -> None:
    app = Canary(UserService)
    await app.init()   # 建图、排序、注入依赖，执行 @on_init
    await app.start()  # 执行 @on_start
    assert app[Database].config is app[Config]
    await app.stop()   # 逆序执行 @on_stop


asyncio.run(main())
```

## 依赖注入

cocoa 通过 `deps=[...]` 声明依赖 —— 无需 `__init__` 装配，也无需额外 DSL。每个依赖在
`init()` 阶段注入为 `self.<snake_case 名>`，所以 `@on_init` 已经能看到自己的协作者：

```python
@cocoa(deps=[Database, Cache])
class UserService:
    @on_init
    def check(self) -> None:
        assert self.database is not None
```

两个依赖的 snake_case 撞名会抛 `InjectionError`，而不是"后写的赢"。

## 生命周期

三个可选钩子 —— 各自同步或异步皆可，每个阶段可有任意多个：

| 阶段 | 装饰器 | 手上有什么 |
|---|---|---|
| 初始化 | `@on_init` | 依赖已就位，但还没有任何东西开始运行 |
| 启动 | `@on_start` | 可以获取资源、起后台任务 |
| 停止 | `@on_stop` | 逆序回收 |

失败路径是设计的一部分：`start()` 失败会逆序回收已启动的单元；`stop()` 是**唯一**的回收
路径，正常结束与失败结束都走它，且可重复调用 —— `finally: await app.stop()` 永远安全。

## Web 应用

`web` 扩展把 `@cocoa` 服务变成 ASGI 应用，并自动生成 OpenAPI 文档：

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService], prefix="/api", tags=["library"])
class LibraryAPI:
    @get("/books/{book_id}")
    async def get_book(self, book_id: int) -> dict: ...

    @post("/books/{book_id}/borrow", status_code=201)
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict: ...


app = Canary(LibraryAPI)  # app 本身就是 ASGI 应用
```

```bash
uvicorn examples.library.web:app --reload
# GET /docs  ·  /openapi.json
```

参数来源只有一条推断规则：**标量走查询串（名字命中路径占位符则走路径），其余走请求体。**
请求头与 cookie 推断不到，用 `Annotated[str, Header()]` 显式声明。handler 必须是
`async def` —— 同步函数会阻塞整个进程，框架在装配期直接拒绝。

签名在**装配期**编译成取值计划，请求路径上没有任何反射。

## 示例

[`examples/`](examples) 下有多个可运行示例，从最小单元逐步到依赖注入、生命周期钩子、
多根编排，以及一个分层的图书馆 web 应用。

## 文档

- [快速开始](docs/zh/quickstart.md)
- [Cocoa 单元](docs/zh/cocoa.md) · [运行时（Canary）](docs/zh/canary.md)
- [生命周期](docs/zh/lifecycle.md) · [依赖注入](docs/zh/dependency-injection.md)
- [Web 应用](docs/zh/web.md) · [架构](docs/zh/architecture.md) · [API 参考](docs/zh/api-reference.md)

## 许可证

Apache-2.0。
