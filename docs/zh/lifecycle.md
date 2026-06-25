# 生命周期管理 (Lifecycle Management)

Canary Framework 提供了一套极简而强大的生命周期系统。你只需要在类中声明特定的同名方法，引擎就会在拓扑排序的适当阶段全自动触发它们。不再需要繁琐的 `@before_startup` 等额外的钩子装饰器。

## 生命周期钩子

你的服务（或模块）可以选择性地实现以下三种方法：

### 1. `def init(self) / async def init(self)`
- **触发时机**：在所有的依赖被 `setattr` 注入完成后立即执行。
- **作用**：用于服务自身的初始化准备工作。因为执行到这里时，所有的外部依赖一定已经就绪。

### 2. `async def startup(self)`
- **触发时机**：ASGI Lifespan 收到 `startup` 事件时，或系统主启动阶段时。按照**正向拓扑顺序**触发（即依赖于别人的服务后启动，被依赖的服务先启动）。
- **作用**：建立数据库长连接、启动后台任务、初始化外部网络资源等。

### 3. `async def shutdown(self)`
- **触发时机**：ASGI Lifespan 收到 `shutdown` 事件时，或系统主动关闭时。按照**逆向拓扑顺序**触发（即依赖于别人的服务先关闭，基础服务最后关闭）。
- **作用**：优雅关闭（Graceful Shutdown），断开数据库连接，释放端口，停止后台任务等。

## 示例

```python
from canary_framework import service
import asyncio

@service()
class Database:
    async def init(self):
        self.connection_string = "postgres://..."

    async def startup(self):
        print(f"Connecting to {self.connection_string}")
        await asyncio.sleep(1) # 模拟连接

    async def shutdown(self):
        print("Disconnecting from database...")
```
