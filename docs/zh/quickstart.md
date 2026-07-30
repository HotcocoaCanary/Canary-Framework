# 快速开始

## 独立 Router

Router 是最小可运行 HTTP 应用。

```python
import asyncio

import uvicorn

from canary_framework import get, router
from canary_framework.core import RouterBase


@router(prefix="/hello", tags=("Hello",))
class HelloRouter(RouterBase):
    @get("")
    async def hello(self) -> dict[str, str]:
        return {"message": "Hello, Canary!"}


async def setup() -> HelloRouter:
    app = HelloRouter()
    await app.init()
    return app


application = asyncio.run(setup())
uvicorn.run(application, lifespan="on")
```

初始化是强制步骤；lifespan 只调用 startup/shutdown。

## 加入领域逻辑

```python
from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

@service()
class Counter(ServiceBase):
    def __init__(self) -> None:
        super().__init__()
        self.value = 0

    async def increment(self) -> int:
        self.value += 1
        return self.value

@router(prefix="/counter")
class CounterRouter(RouterBase):
    counter: Counter

    @get("")
    async def increment(self) -> dict[str, int]:
        return {"value": await self.counter.increment()}

@module(children=(CounterRouter,))
class App(ModuleBase):
    pass
```

Module 只列 Router；`Counter` 从注解传递发现。逻辑需要复用或独立测试时再提取为 Service。

## 生命周期

结构状态放在异步 `on_init`，事件循环资源放在 `on_startup`，清理放在 `on_shutdown`。不要覆盖公开的 `init`、`startup`、`shutdown`。

下一步可阅读可运行示例和 [API 参考](api-reference.md)。
