# Canary Framework

一个极简、装饰器驱动的**依赖注入**与**生命周期**运行时 —— 纯 Python，零依赖。

它**不是 web 框架**，是一个运行时容器：负责把一堆对象按依赖关系装配起来、按序启动、按逆序
回收。至于这些对象最后被什么外壳驱动（HTTP、CLI、定时任务、消息消费者），那是外壳的事 ——
用 FastAPI、Starlette、Typer、你自己的 `main()` 都行。

框架只有两个概念：

- **cocoa** —— 最小单元。被 `@cocoa` 标记的普通 class；依赖由 `deps=[...]` 声明，行为由
  `@on_init` / `@on_start` / `@on_stop` 钩子定义。
- **Canary** —— 编排器。`Canary(*roots)` 解析依赖图、拓扑排序、驱动完整生命周期。

## 一条贯穿全框架的规则

> **框架只造空壳，一切需要外界输入的事都在生命周期里做。**

单元一律由框架**无参构造** —— 所以 `__init__` 不能有必填参数。需要什么就声明成依赖，值在
`@on_init` 或 `@on_start` 里从协作者那里读。这条约束不是限制：构造函数没有对手（`@on_start`
有 `@on_stop` 配对，"构造"却没有"析构"），把需要输入的事推迟到生命周期里，等于让每一件事
都落进一个有台账、能逆序回收的阶段。

## 亮点

- **声明式依赖注入** —— 无需 `__init__` 装配；依赖在**构造期**注入为
  `self.<snake_case 名>`，所以 `@on_init` 已经能看到自己的协作者。
- **显式、异步原生生命周期** —— 装配在构造期，然后 `start()` → `stop()`；同步/异步钩子皆可。
  接进任何宿主只要一行 `async with canary:`。
- **失败路径是设计的一部分** —— `start()` 失败会逆序回收已启动的单元；`stop()` 是唯一的
  回收路径，正常结束与失败结束都走它，且可重复调用。
- **确定性排序** —— 卡恩拓扑排序；每个类型在图内共享同一个单例。
- **多根编排** —— 嵌套、混入，或独立启动任意子图。
- **零依赖** —— `pip install canary-framework` 不拉进任何第三方包，只用标准库。这条有测试
  守着：跑完一整轮生命周期后，`sys.modules` 里不该出现任何来自 site-packages 的东西。
- **装配很快** —— 1000 个单元建图 + 注入 + `@on_init` 约 2.4 ms；框架自身的导入耗时 0.0 ms。

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
    await app.start()  # 跑 @on_init，再跑 @on_start
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
- [架构](architecture.md)
- [API 参考](api-reference.md)
