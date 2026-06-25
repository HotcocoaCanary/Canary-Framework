# 生命周期管理

Canary Framework 为服务和模块提供全面的生命周期管理系统。

## 生命周期阶段

每个服务和模块都经历以下阶段：

```
实例化 → 初始化 → 启动 → 关闭
```

### 1. 实例化

服务实例通过 `__init__()` 创建：

```python
@service()
class MyService(ServiceBase):
    def __init__(self):
        self.connected = False
        self.data = []
```

### 2. 初始化

所有服务实例化后调用 `init()` 方法。重写它来建立连接、填充种子数据或执行任何实例化后的设置：

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class UserService(ServiceBase):
    db: Database

    async def init(self):
        await super().init()
        if not await self.db.has_users():
            await self.db.create_default_users()
```

### 3. 启动

应用准备好启动时调用 `startup()` 方法：

```python
@service()
class MyService(ServiceBase):
    async def startup(self):
        pass
```

使用 `async def startup(self):\n        await super().startup()` 钩子在启动前运行代码：

```python
from canary_framework import before_startup

@service()
class Server(ServiceBase):
    async def startup(self):\n        await super().startup()
    async def verify_connections(self):
        assert self.db.connection is not None
        assert self.cache.connection is not None
```

### 4. 关闭

应用停止时调用 `shutdown()` 方法：

```python
@service()
class MyService(ServiceBase):
    async def shutdown(self):
        pass
```

使用 `async def shutdown(self):\n        await super().shutdown()` 钩子在关闭前运行代码：

```python
from canary_framework import before_shutdown

@service()
class Database(ServiceBase):
    async def shutdown(self):\n        await super().shutdown()
    async def disconnect(self):
        await self.connection.close()
```

## 生命周期钩子

有两个装饰器可用于钩住生命周期：

| 装饰器 | 阶段 | 时机 |
|-----------|-------|--------|
| `async def startup(self):\n        await super().startup()` | 启动 | `startup()` 调用前 |
| `async def shutdown(self):\n        await super().shutdown()` | 关闭 | `shutdown()` 调用前 |

## 钩子方法

钩子可以是同步的或异步的：

```python
@service()
class MyService(ServiceBase):
    async def startup(self):\n        await super().startup()
    async def async_hook(self):
        await some_async_operation()
```

## 模块生命周期

模块协调其子服务的生命周期：

```python
@module(services=[ServiceA, ServiceB])
class App(ModuleBase):
    pass

app = App()

# 初始化所有服务
await app.init()

# 启动所有服务
await app.startup()

# ... 运行应用 ...

# 按逆序关闭所有服务
await app.shutdown()
```

执行顺序遵循拓扑排序：
- **初始化**：依赖先执行（A → B）
- **启动**：依赖先执行（A → B）
- **关闭**：逆序执行（B → A）

## 完整生命周期示例

```python
from canary_framework import (
    service, module,
    before_startup, before_shutdown
)
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase

calls = []

@service()
class A(ServiceBase):
    async def init(self):
        await super().init()
        calls.append("A: init")

    async def startup(self):\n        await super().startup()
    def startup_a(self):
        calls.append("A: before_startup")

    async def shutdown(self):\n        await super().shutdown()
    def shutdown_a(self):
        calls.append("A: before_shutdown")

@service()
class B(ServiceBase):
    a: A  # B 依赖 A

    async def init(self):
        await super().init()
        calls.append("B: init")

    async def startup(self):\n        await super().startup()
    def startup_b(self):
        calls.append("B: before_startup")

    async def shutdown(self):\n        await super().shutdown()
    def shutdown_b(self):
        calls.append("B: before_shutdown")

@module(services=[A, B])
class App(ModuleBase):
    pass

# 运行生命周期
app = App()
await app.init()
await app.startup()
await app.shutdown()

# 结果顺序：
# A: init
# B: init
# A: before_startup
# B: before_startup
# B: before_shutdown
# A: before_shutdown
```

## ASGI 生命周期

作为 ASGI 应用运行时，框架通过 `ServiceBase.__call__` 处理生命周期：

```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8000

@module(services=[AppConfig, ...])
class App(ModuleBase):
    config: AppConfig

async def setup():
    app = App()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn

    app = asyncio.run(setup())
    uvicorn.run(app, host="0.0.0.0", port=8000, lifespan="on")
```

`ServiceBase.__call__` 处理 ASGI lifespan：
1. 服务器启动时调用 `startup()`
2. 服务器停止时调用 `shutdown()`

## 配置

Config 是普通的 DI 服务。将其加入模块并通过注解注入：

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    database_url: str = "sqlite:///mydb.db"
    debug: bool = True

@service()
class Database(ServiceBase):
    config: AppConfig

    async def init(self):
        await super().init()
        url = self.config.database_url
        self.connection = await connect(url)

app = App()
await app.init()
await app.startup()
await app.shutdown()
```

框架在 `init()` 期间自动配置日志。无需手动调用
`logging.basicConfig()`。

**默认行为**：当您调用 `app.init()` 时，框架为 `cf` 日志器添加
`StreamHandler`，默认级别为 `INFO`：

```python
from canary_framework import module

@module(services=[AppConfig, ...])
class App(ModuleBase):
    config: AppConfig

app = App()
await app.init()
# 框架日志现在显示在 stdout 上：
# [2026-06-02 13:00:00] cf.module             INFO     Initializing module: AppModule
```

**自定义日志级别**：在配置对象上设置 `log_level` 来控制
框架日志级别：

```python
@config()
class AppConfig(CanaryConfig):
    log_level: str = "DEBUG"  # 显示 debug 级别的框架日志
    # ... 其他配置字段 ...
```

有效级别：`"DEBUG"`、`"INFO"`、`"WARNING"`、`"ERROR"`、`"CRITICAL"`。

**手动处理器**：如果您已经在 root 日志器或 `cf` 日志器上配置了 handler，
框架会跳过自己的设置。

## 错误处理

如果钩子引发异常，它会被包装在 `CanaryFrameworkError` 中：

```python
from canary_framework.common import CanaryFrameworkError

try:
    await app.init()
except CanaryFrameworkError as e:
    print(f"生命周期错误：{e}")
```

## 最佳实践

1. **重写 `init()` 建立连接和设置数据**：初始化期间建立连接和设置初始数据
2. **使用 `async def startup(self):\n        await super().startup()` 进行验证**：提供服务前验证一切就绪
3. **使用 `async def shutdown(self):\n        await super().shutdown()` 进行清理**：优雅关闭连接并保存状态
4. **保持钩子专注**：每个钩子应该只做好一件事
5. **优雅处理错误**：在钩子中捕获并记录异常
