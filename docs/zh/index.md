# Canary Framework

一个极简、装饰器驱动的 **依赖注入**、**生命周期** 与 **ASGI Web 应用** 框架 —— 纯 Python。

框架只有两个概念：

- **cocoa** —— 最小单元。被 `@cocoa` 标记的普通 class；依赖由 `deps=[...]` 声明，行为由
  `@on_init` / `@on_start` / `@on_stop` 钩子定义。
- **Canary** —— 编排器。`Canary(*roots)` 解析依赖图、拓扑排序、驱动完整生命周期；它本身
  也是一个 ASGI 应用。

## 一条贯穿全框架的规则

> **框架只造空壳，一切需要外界输入的事都在生命周期里做。**

单元一律由框架**无参构造** —— 所以 `__init__` 不能有必填参数。需要什么就声明成依赖，值在
`@on_init` 或 `@on_start` 里从协作者那里读。这条约束不是限制：构造函数没有对手（`@on_start`
有 `@on_stop` 配对，"构造"却没有"析构"），把需要输入的事推迟到生命周期里，等于让每一件事
都落进一个有台账、能逆序回收的阶段。

## 亮点

- **声明式依赖注入** —— 无需 `__init__` 装配；依赖在 `init()` 阶段注入为
  `self.<snake_case 名>`，所以 `@on_init` 已经能看到自己的协作者。
- **显式、异步原生生命周期** —— `init()` → `start()` → `stop()`；同步/异步钩子皆可。
- **失败路径是设计的一部分** —— `start()` 失败会逆序回收已启动的单元；`stop()` 是唯一的
  回收路径，正常结束与失败结束都走它，且可重复调用。
- **确定性排序** —— 卡恩拓扑排序；每个类型在图内共享同一个单例。
- **多根编排** —— 嵌套、混入，或独立启动任意子图。
- **可选 web 扩展** —— `@web_cocoa` + `@get`/`@post` 把单元变成 ASGI 应用并自动生成
  OpenAPI 文档。签名在**装配期**编译成取值计划，请求路径上没有任何反射。
- **核心零依赖** —— `pip install canary-framework` 不会拉进任何第三方包；starlette 与
  pydantic 只属于 `[web]` 扩展。

## 示例

```python
import asyncio

from canary_framework import Canary, cocoa, on_init, on_start


@cocoa
class Config:
    def __init__(self) -> None:  # 无参构造：没有必填参数
        self.database_url = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        self.pool = ConnectionPool(self.config.database_url)  # self.config 已注入

    @on_start
    async def connect(self) -> None:
        await self.pool.connect()


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

## 导航

- [快速开始](quickstart.md)
- [Cocoa 单元](cocoa.md)
- [运行时（Canary）](canary.md)
- [生命周期](lifecycle.md)
- [依赖注入](dependency-injection.md)
- [Web 应用](web.md)
- [架构](architecture.md)
- [API 参考](api-reference.md)
