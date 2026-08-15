# 快速开始

安装框架：

```bash
pip install canary-framework
```

需要 Python 3.12+。

## 声明单元

用 `@cocoa` 标记任意普通 class，依赖通过 `deps=[...]` 声明：

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    # self.config 会在 start() 阶段注入
    def __init__(self) -> None:
        self.pool = None
```

## 添加生命周期行为

使用 `@on_init`、`@on_start`、`@on_stop` —— 均可选，同步或异步皆可：

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def setup(self) -> None:
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

## 用 `Canary` 运行

`Canary(*roots)` 从每个根解析依赖图、拓扑排序，并显式驱动生命周期：

```python
import asyncio

from canary_framework import Canary, cocoa


@cocoa(deps=[Database])
class UserService: ...


async def main() -> None:
    app = Canary(UserService)
    await app.init()
    await app.start()

    try:
        users = app[UserService]
        assert users.database is app[Database]
    finally:
        await app.stop()


asyncio.run(main())
```

也可用异步上下文管理器：

```python
async def main() -> None:
    async with Canary(UserService) as app:
        assert app[Database] is app[UserService].database


asyncio.run(main())
```

## 组合多个根

`Canary` 接受多个根，把它们的依赖图合并为一张：

```python
app = Canary(UserService, ReportService)
await app.start()
assert app[Database] is app[UserService].database
```

任意子图都可独立启动 —— `Canary(Database)` 只会启动 `Database` 及其依赖（`Config`）。

## 暴露为 Web 应用

安装可选的 `web` 扩展，把单元以 HTTP 暴露：

```bash
pip install "canary-framework[web]"
```

```python
from canary_framework import Canary
from canary_framework.web import get, web_cocoa


@web_cocoa(deps=[Database])
class LibraryAPI:
    @get("/books")
    async def list_books(self) -> list[dict]:
        return self.database.all("books")


app = Canary(LibraryAPI)  # app 本身就是 ASGI 应用
```

```bash
uvicorn examples.library.web:app --reload
```

打开 `/docs` 查看交互式 OpenAPI 文档。详见 [Web 应用](web.md)。

## 下一步

- [Cocoa 单元](cocoa.md) —— 声明、依赖与钩子。
- [运行时（Canary）](canary.md) —— 编排、多根与 ASGI。
- [生命周期](lifecycle.md) —— 状态机与钩子顺序。
- [依赖注入](dependency-injection.md) —— 注入、共享、成环。
