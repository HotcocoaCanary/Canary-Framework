# Canary Framework 0.6

Canary 围绕三个显式层次构建：

1. **Service**：生命周期、依赖注入、领域逻辑；永远不是 ASGI。
2. **Router**：可消费 Service 依赖并声明 HTTP 路由；最小可运行应用。
3. **Module**：显式子节点组合与依赖作用域边界；递归聚合 Router 后代。

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

## 核心保证

- 显式异步初始化；lifespan 绝不初始化。
- 基于类型注解的 DI、方向校验与确定性拓扑顺序。
- 父作用域复用、兄弟隔离、显式 Service 提升。
- prefix、tags、security 确定性传播。
- 每个运行根只有一张路由表与一份 OpenAPI。
- 路由、文档路径、operation ID、安全方案、schema 冲突在编译期检查。

继续阅读[快速开始](quickstart.md)、[服务](services.md)、[模块](modules.md)与[路由](web.md)。
