# 快速开始

安装框架：

```bash
pip install canary-framework
```

需要 Python 3.12+。核心零依赖 —— 不会拉进任何第三方包。

## 声明单元

用 `@cocoa` 标记任意普通 class，依赖通过 `deps=[...]` 声明：

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:      # 无参构造：不能有必填参数
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    # self.config 在 init() 阶段注入
    pass
```

单元一律由框架**无参构造**，所以需要什么值就声明成依赖，在生命周期钩子里从协作者那里读 ——
不要写成构造参数。

## 添加生命周期行为

使用 `@on_init`、`@on_start`、`@on_stop` —— 均可选，同步或异步皆可：

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def setup(self) -> None:
        # 依赖已就位，但还没有任何东西开始运行
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        # 要连接、要起后台任务的，归这里
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

判据：不碰外部资源的准备工作放 `@on_init`，需要获取资源的放 `@on_start` —— 因为只有
`@on_start` 拿到的东西才会被 `@on_stop` 回收。

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
        await app.stop()      # 从任何终态都能调，幂等


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
await app.init()
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


@web_cocoa(deps=[Database], prefix="/api")
class LibraryAPI:
    @get("/books")
    async def list_books(self) -> list[dict]:       # handler 必须是 async def
        return self.database.all("books")


app = Canary(LibraryAPI)  # app 本身就是 ASGI 应用
```

```bash
uvicorn examples.library.web:app --reload
```

打开 `/docs` 查看交互式 OpenAPI 文档。详见 [Web 应用](web.md)。

## 看看框架装配出了什么

把日志级别设成 `DEBUG`，启动末尾会打印一份装配摘要（启动顺序、依赖、路由）：

```bash
CANARY_LOG_LEVEL=DEBUG python -m examples.library.main
```

## 下一步

- [Cocoa 单元](cocoa.md) —— 声明、构造规则与钩子。
- [运行时（Canary）](canary.md) —— 编排、多根与 ASGI。
- [生命周期](lifecycle.md) —— 五个时刻、状态机与失败路径。
- [依赖注入](dependency-injection.md) —— 注入、共享、成环、撞名。
