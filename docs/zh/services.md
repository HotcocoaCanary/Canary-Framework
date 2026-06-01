# 服务

服务是 Canary 框架应用程序的构建块。它们封装业务逻辑，可以组合在一起形成复杂的系统。

## 定义服务

使用 `@service` 装饰器定义服务：

```python
from canary_framework import service

@service(name="user_repository")
class UserRepository:
    def __init__(self):
        self.users = []
    
    async def get_all(self):
        return self.users
    
    async def add(self, user):
        self.users.append(user)
        return user
```

### 服务参数

- `name`：（必需）服务的唯一标识符
- `deps`：（可选）此服务依赖的服务类列表

## 服务依赖

服务可以依赖于其他服务。使用 `deps` 参数声明依赖：

```python
@service(name="database")
class DatabaseService:
    pass

@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        # 数据库服务自动注入为 self.database_service
        return await self.database_service.query(...)
```

依赖项以 snake_case 格式自动注入为属性：
- `DatabaseService` → `self.database_service`
- `UserRepository` → `self.user_repository`

## 服务生命周期

服务经过明确定义的生命周期：

1. **实例化**：创建服务实例
2. **配置**：调用 `configure()` 方法
3. **初始化**：调用 `init()` 方法
4. **启动**：调用 `startup()` 方法
5. **关闭**：调用 `shutdown()` 方法（应用停止时）

您可以使用生命周期钩子进入这些阶段。有关详细信息，请参阅[生命周期](./lifecycle.md)文档。

## 服务基类

当您用 `@service` 装饰一个类时，它会自动继承自 `ServiceBase`，该类提供：

- `config` 属性：访问配置阶段传递的配置
- `configure(config)` 方法：配置服务
- `init()` 方法：初始化服务
- `startup()` 方法：启动服务
- `shutdown()` 方法：关闭服务

## 完整示例

```python
from canary_framework import service, after_config, after_init, before_startup, before_shutdown

@service(name="cache")
class CacheService:
    def __init__(self):
        self.cache = {}
        self.connection = None
    
    @after_config
    async def connect(self):
        # 连接到缓存服务器
        self.connection = "connected"
        print("Cache connected")
    
    @after_init
    async def warmup(self):
        # 用常用数据预热缓存
        self.cache["default"] = {"value": "default"}
        print("Cache warmed up")
    
    @before_startup
    async def verify(self):
        # 验证缓存已准备就绪
        assert self.connection is not None
        print("Cache verified")
    
    @before_shutdown
    async def cleanup(self):
        # 清理资源
        self.connection = None
        print("Cache disconnected")
    
    async def get(self, key):
        return self.cache.get(key)
    
    async def set(self, key, value):
        self.cache[key] = value
```

## 测试服务

服务易于测试，因为它们是普通的 Python 类：

```python
import pytest

@pytest.mark.asyncio
async def test_cache_service():
    service = CacheService()
    await service.configure()
    await service.init()
    await service.startup()
    
    await service.set("key", "value")
    assert await service.get("key") == "value"
    
    await service.shutdown()
```

## 服务命名

服务名称在模块内必须唯一。框架会自动将类名转换为 snake_case 格式作为注入属性名：

| 类名 | 注入属性名 |
|------|------------|
| `DatabaseService` | `self.database_service` |
| `UserRepository` | `self.user_repository` |
| `APIRouter` | `self.api_router` |

## 最佳实践

1. **单一职责**：每个服务应该只负责一件事
2. **无状态设计**：尽量使服务无状态，或明确管理状态
3. **依赖最小化**：只声明真正需要的依赖
4. **类型提示**：使用类型提示提高代码可读性和 IDE 支持
5. **测试覆盖**：为每个服务编写单元测试
