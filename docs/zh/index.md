# Canary Framework

一个极简、装饰器驱动的 **依赖注入**、**生命周期** 与 **ASGI Web 应用** 框架 —— 纯 Python。

框架只有两个概念：

- **cocoa** —— 最小单元。被 `@cocoa` 标记的普通 class；依赖由 `deps=[...]` 声明，行为由
  `@on_init` / `@on_start` / `@on_stop` 钩子定义。
- **Canary** —— 编排器。`Canary(*roots)` 解析依赖图、拓扑排序、驱动完整生命周期；它本身
  也是一个 ASGI 应用。

## 亮点

- **惰性依赖注入** —— 无需 `__init__` 装配；依赖在 `start()` 阶段注入为
  `self.<snake_case 名>`。
- **显式、异步原生生命周期** —— `init()` → `start()` → `stop()`；同步/异步钩子皆可。
- **确定性排序** —— 卡恩拓扑排序；每个类型在图内共享同一个单例。
- **多根编排** —— 嵌套、混入，或独立启动任意子图。
- **可选 web 扩展** —— `@web_cocoa` + `@get`/`@post` 把单元变成 FastAPI 风格的 ASGI 应用，
  并自动生成 OpenAPI 文档。

## 示例

```python
import asyncio

from canary_framework import Canary, cocoa, on_start


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_start
    async def connect(self) -> None:
        await self.pool.connect()  # self.config 已注入


@cocoa(deps=[Database])
class UserService: ...


async def main() -> None:
    app = Canary(UserService)
    await app.init()  # 建图，执行 @on_init
    await app.start()  # 注入依赖，执行 @on_start
    assert app[Database].config is app[Config]
    await app.stop()  # 逆序执行 @on_stop


asyncio.run(main())
```

## 导航

- [快速开始](quickstart.md)
- [Cocoa 单元](cocoa.md)
- [运行时（Canary）](canary.md)
- [生命周期](lifecycle.md)
- [依赖注入](dependency-injection.md)
- [Web 应用](web.md)
- [架构](architecture.md)
- [API 参考](api-reference.md)
