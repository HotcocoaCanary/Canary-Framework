# 生命周期管理

Canary 框架为服务和模块提供全面的生命周期管理系统。

## 生命周期阶段

每个服务和模块都经过这些阶段：

```
实例化 → 配置 → 初始化 → 启动 → 关闭
```

### 1. 实例化

使用 `__init__()` 创建服务实例：

```python
@service(name="my_service")
class MyService:
    def __init__(self):
        # 初始化基本属性
        self.connected = False
        self.data = []
```

### 2. 配置

调用 `configure(config)` 方法，您可以在其中设置连接和访问配置：

```python
@service(name="my_service")
class MyService:
    async def configure(self, config_instance=None):
        # 访问配置
        if config_instance:
            self.config = config_instance
```

使用 `@after_config` 钩子在配置后运行代码：

```python
from canary_framework import after_config

@service(name="database")
class DatabaseService:
    @after_config
    async def connect(self):
        # 连接到数据库
        self.connection = await connect_to_db(self.config.db_url)
```

### 3. 初始化

在所有服务配置后调用 `init()` 方法：

```python
@service(name="my_service")
class MyService:
    async def init(self):
        # 在所有依赖项准备好后初始化服务
        pass
```

使用 `@after_init` 钩子在初始化后运行代码：

```python
from canary_framework import after_init

@service(name="user_service")
class UserService:
    @after_init
    async def seed_default_users(self):
        # 如果需要，创建默认用户
        if not await self.db.has_users():
            await self.db.create_default_users()
```

### 4. 启动

当应用准备好启动时调用 `startup()` 方法：

```python
@service(name="my_service")
class MyService:
    async def startup(self):
        # 启动后台任务，开始处理等
        pass
```

使用 `@before_startup` 钩子在启动前运行代码：

```python
from canary_framework import before_startup

@service(name="server")
class ServerService:
    @before_startup
    async def verify_connections(self):
        # 在提供服务前验证所有连接正常
        assert self.db.connection is not None
        assert self.cache.connection is not None
```

### 5. 关闭

当应用停止时调用 `shutdown()` 方法：

```python
@service(name="my_service")
class MyService:
    async def shutdown(self):
        # 清理资源
        pass
```

使用 `@before_shutdown` 钩子在关闭前运行代码：

```python
from canary_framework import before_shutdown

@service(name="database")
class DatabaseService:
    @before_shutdown
    async def disconnect(self):
        # 优雅断开连接
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
@service(name="my_service")
class MyService:
    @after_config
    def sync_hook(self):
        # 同步钩子
        print("Configured")
    
    @after_init
    async def async_hook(self):
        # 异步钩子
        await some_async_operation()
```

## 模块生命周期

模块协调其子服务的生命周期：

```python
@module(name="app", services=[ServiceA, ServiceB])
class AppModule:
    pass

app = AppModule()

# 按依赖顺序配置所有服务
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
- **配置**：A → B
- **初始化**：A → B
- **启动**：A → B
- **关闭**：B → A

## 完整生命周期示例

```python
from canary_framework import (
    service, module,
    after_config, after_init, before_startup, before_shutdown
)

calls = []

@service(name="a")
class ServiceA:
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

@service(name="b", deps=[ServiceA])
class ServiceB:
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

@module(name="app", services=[ServiceA, ServiceB])
class AppModule:
    pass

# 运行生命周期
app = AppModule()
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
import uvicorn

@module(name="app", services=[...])
class AppModule:
    pass

# uvicorn 处理生命周期事件
uvicorn.run("main:AppModule", lifespan="on")
```

ASGI 生命周期协议将：
1. 服务器启动时调用 `startup()`
2. 服务器停止时调用 `shutdown()`

## 配置

在配置阶段传递配置：

```python
class AppConfig:
    def __init__(self):
        self.database_url = "sqlite:///mydb.db"
        self.debug = True

@service(name="database")
class DatabaseService:
    @after_config
    async def connect(self):
        # 通过 self.config 访问配置
        url = self.config.database_url
        self.connection = await connect(url)

app = AppModule()
await app.configure(AppConfig())
```

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
