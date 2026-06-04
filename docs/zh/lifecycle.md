# 生命周期管理

Canary 框架为服务和模块提供全面的生命周期管理系统。

## 生命周期阶段

每个服务和模块都经过这些阶段：

```
实例化 → configure(config_instance) → init() → startup() → shutdown()
```

### 1. 实例化

使用 `__init__()` 创建服务实例：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    def __init__(self):
        self.connected = False
        self.data = []
```

### 2. 配置

调用 `configure(config_instance)` 方法。对于模块，此阶段会：
- 创建注册表并递归注册所有子服务及其依赖
- 执行拓扑排序
- 实例化所有服务
- 解析并注入依赖
- 按顺序调用每个服务的 `configure()`

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    async def configure(self, config_instance=None):
        if config_instance:
            self.config = config_instance
```

使用 `@after_config` 钩子在配置后运行代码：

```python
from canary_framework import after_config, service
from canary_framework.core import ServiceBase

@service()
class Database(ServiceBase):
    @after_config
    async def connect(self):
        self.connection = await connect_to_db(self.config.db_url)
```

### 3. 初始化

在所有服务配置后调用 `init()` 方法。对于模块，按拓扑顺序传播到所有子服务：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    async def init(self):
        pass
```

使用 `@after_init` 钩子在初始化后运行代码：

```python
from canary_framework import after_init, service
from canary_framework.core import ServiceBase

@service()
class UserService(ServiceBase):
    @after_init
    async def seed_default_users(self):
        if not await self.db.has_users():
            await self.db.create_default_users()
```

### 4. 启动

当应用准备好启动时调用 `startup()` 方法。对于模块，按拓扑顺序传播：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    async def startup(self):
        pass
```

使用 `@before_startup` 钩子在启动前运行代码：

```python
from canary_framework import before_startup, service
from canary_framework.core import ServiceBase

@service()
class Server(ServiceBase):
    @before_startup
    async def verify_connections(self):
        assert self.db.connection is not None
        assert self.cache.connection is not None
```

### 5. 关闭

当应用停止时调用 `shutdown()` 方法。对于模块，按**逆拓扑顺序**传播：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    async def shutdown(self):
        pass
```

使用 `@before_shutdown` 钩子在关闭前运行代码：

```python
from canary_framework import before_shutdown, service
from canary_framework.core import ServiceBase

@service()
class Database(ServiceBase):
    @before_shutdown
    async def disconnect(self):
        await self.connection.close()
```

## 生命周期钩子

有四个装饰器可用于钩住生命周期：

| 装饰器 | 阶段 | 时机 |
|--------|------|------|
| `@after_config` | 配置 | `configure()` 调用后 |
| `@after_init` | 初始化 | `init()` 调用后 |
| `@before_startup` | 启动 | `startup()` 调用前 |
| `@before_shutdown` | 关闭 | `shutdown()` 调用前 |

## 钩子方法

钩子可以是同步的或异步的：

```python
from canary_framework import service, after_config, after_init
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    @after_config
    def sync_hook(self):
        print("Configured")

    @after_init
    async def async_hook(self):
        await some_async_operation()
```

## 模块生命周期

模块协调其子服务的生命周期。`configure()` 阶段是 DI 的核心：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[ServiceA, ServiceB])
class App(ModuleBase):
    pass

app = App()

# 按依赖顺序配置所有服务（包含 DI 注入）
await app.configure(config)

# 初始化所有服务
await app.init()

# 启动所有服务
await app.startup()

# ... 运行应用 ...

# 按相反顺序关闭所有服务
await app.shutdown()
```

执行顺序遵循拓扑排序：
- **configure**: A → B（包含 DI 注入：解析注解 → setattr 注入）
- **init**: A → B
- **startup**: A → B
- **shutdown**: B → A（逆序）

### 配置阶段详细步骤

```
module.configure(config_instance)
├─ 1. 设置 config 属性
├─ 2. 初始化日志（从 config_instance.log_level 读取级别）
├─ 3. 创建 Registry（可继承父注册表）
├─ 4. 递归注册服务（_register_entry_with_deps）
│   ├─ 检查幂等性（已在注册表则跳过）
│   ├─ 注册到 Registry
│   └─ 通过 resolve_deps(cls) 读取类型注解，递归注册依赖
├─ 5. topological_sort(registry) — 构建依赖图并排序
├─ 6. 按拓扑顺序实例化所有服务
├─ 7. 按拓扑顺序注入依赖
│   └─ for attr_name, dep_cls in resolve_deps(type(inst)).items():
│       setattr(inst, attr_name, registry.get_by_class(dep_cls).instance)
├─ 8. 通过 setattr(self, entry.cls.__name__, inst) 挂载子服务
├─ 9. 按拓扑顺序调用每个子服务的 configure(config_instance)
└─ 10. 调用模块自身的 @after_config 钩子
```

## 完整生命周期示例

```python
from canary_framework import (
    service, module,
    after_config, after_init, before_startup, before_shutdown
)
from canary_framework.core import ServiceBase, ModuleBase

calls = []

@service()
class A(ServiceBase):
    @after_config
    def config_a(self):
        calls.append("A: after_config")

    @after_init
    def init_a(self):
        calls.append("A: after_init")

    @before_startup
    def startup_a(self):
        calls.append("A: before_startup")

    @before_shutdown
    def shutdown_a(self):
        calls.append("A: before_shutdown")

@service()
class B(ServiceBase):
    a: AService  # B 依赖 A

    @after_config
    def config_b(self):
        calls.append("B: after_config")

    @after_init
    def init_b(self):
        calls.append("B: after_init")

    @before_startup
    def startup_b(self):
        calls.append("B: before_startup")

    @before_shutdown
    def shutdown_b(self):
        calls.append("B: before_shutdown")

@module(services=[AService, BService])
class App(ModuleBase):
    pass

app = App()
await app.configure()
await app.init()
await app.startup()
await app.shutdown()

# 结果顺序：
# A: after_config
# B: after_config
# A: after_init
# B: after_init
# A: before_startup
# B: before_startup
# B: before_shutdown
# A: before_shutdown
```

## ASGI 生命周期

作为 ASGI 应用运行时，框架会自动处理生命周期：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8000

@module(services=[...])
class App(ModuleBase):
    pass

async def setup():
    cfg = AppConfig()
    app = App()
    await app.configure(cfg)
    await app.init()
    return app, cfg

if __name__ == "__main__":
    import asyncio
    import uvicorn

    app, cfg = asyncio.run(setup())
    uvicorn.run(app, host=cfg.host, port=cfg.port, lifespan="on")
```

ASGI 生命周期协议将：
1. 服务器启动时调用 `startup()`
2. 服务器停止时调用 `shutdown()`

注意：`configure()` 和 `init()` 需要在 uvicorn 启动前手动调用，或者通过自定义启动脚本管理。

## 配置

在配置阶段传递配置对象：

```python
from canary_framework import service, module
from canary_framework.core import ServiceBase, ModuleBase

from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    database_url: str = "sqlite:///mydb.db"
    debug: bool = True

@service()
class Database(ServiceBase):
    @after_config
    async def connect(self):
        url = self.config.database_url
        self.connection = await connect(url)

app = App()
await app.configure(AppConfig())
```

### 日志配置

框架在 `configure()` 阶段自动配置日志，无需手动调用 `logging.basicConfig()`。

**默认行为**：调用 `app.configure(config)` 时，框架自动为 `cf` 日志器添加
`StreamHandler`，默认级别为 `INFO`：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[...])
class App(ModuleBase):
    pass

from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    database_url: str = "sqlite:///mydb.db"

app = App()
await app.configure(AppConfig())
# 框架日志现在会输出到 stdout：
# [2026-06-02 13:00:00] cf.module             INFO     Configuring module: App
```

**自定义日志级别**：在配置对象上设置 `log_level` 字段来控制框架日志级别：

```python
@config
class AppConfig(CanaryConfig):
    log_level: str = "DEBUG"
    # ... 其他配置字段 ...
```

有效级别：`"DEBUG"`、`"INFO"`、`"WARNING"`、`"ERROR"`、`"CRITICAL"`。

**手动处理器**：如果你已经为 root 日志器或 `cf` 日志器配置了 handler，框架会跳过
自动设置，让你可以自由使用自己的日志配置。

## 错误处理

如果钩子抛出异常，它会被包装在 `LifecycleHookError` 中：

```python
from canary_framework.common import LifecycleHookError

try:
    await app.configure()
except LifecycleHookError as e:
    print(f"Lifecycle error: {e}")
```

## 最佳实践

1. **使用 `@after_config` 连接**：配置后建立连接
2. **使用 `@after_init` 设置数据**：依赖项准备好后设置初始数据
3. **使用 `@before_startup` 验证**：提供服务前验证一切就绪
4. **使用 `@before_shutdown` 清理**：优雅关闭连接并保存状态
5. **保持钩子专注**：每个钩子做好一件事
6. **优雅处理错误**：在钩子中捕获并记录异常
