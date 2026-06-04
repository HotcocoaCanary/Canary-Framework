# 服务

服务是 Canary 框架应用程序的构建块。它们封装业务逻辑，可以组合在一起形成复杂的系统。

## 定义服务

使用 `@service()` 装饰器定义服务（无参数调用）：

```python
from canary_framework import service

@service()
class UserRepository:
    def __init__(self):
        self.users = []

    async def get_all(self):
        return self.users

    async def add(self, user):
        self.users.append(user)
        return user
```

### 自动命名

服务名称自动生成为 `类名 + "Service"`：

| 类名 | 自动生成的服务名 |
|------|-----------------|
| `UserRepository` | `UserRepositoryService` |
| `Database` | `DatabaseService` |
| `Cache` | `CacheService` |

## 服务依赖

依赖通过 Python 类型注解声明，取代了旧的 `deps` 参数。只需在类体中添加带类型的属性注解即可：

```python
@service()
class Database:
    pass

@service()
class UserService:
    db: DatabaseService  # 依赖声明：通过类型注解

    async def get_user(self, user_id):
        return await self.db.query(...)
```

框架会自动：
1. 通过 `resolve_deps(cls)` 读取类型注解
2. 识别被 `@service`/`@module`/`@router` 装饰的依赖类型
3. 递归注册依赖到注册表
4. 拓扑排序后按顺序实例化
5. 将实例按注解键名注入（如 `self.db`）

**关键区别**：注入的属性名由您控制的注解键名决定，而不是框架自动生成的 snake_case。例如：
- `db: DatabaseService` → 通过 `self.db` 访问
- `cache: CacheService` → 通过 `self.cache` 访问
- `auth: AuthService` → 通过 `self.auth` 访问

## 服务生命周期

服务经过明确定义的生命周期：

1. **实例化**：创建服务实例
2. **配置**：调用 `configure(config_instance)` 方法
3. **初始化**：调用 `init()` 方法
4. **启动**：调用 `startup()` 方法
5. **关闭**：调用 `shutdown()` 方法（应用停止时）

您可以使用生命周期钩子介入这些阶段。有关详细信息，请参阅[生命周期](./lifecycle.md)文档。

## 服务基类

当您用 `@service()` 装饰一个类时，它会自动继承自 `ServiceBase`，该类提供：

- `config` 属性：访问配置阶段传递的配置
- `configure(config_instance=None)` 方法：配置服务
- `init()` 方法：初始化服务
- `startup()` 方法：启动服务
- `shutdown()` 方法：关闭服务

## 完整示例

```python
from canary_framework import service, after_config, after_init, before_startup, before_shutdown

@service()
class Cache:
    def __init__(self):
        self.cache = {}
        self.connection = None

    @after_config
    async def connect(self):
        self.connection = "connected"
        print("Cache connected")

    @after_init
    async def warmup(self):
        self.cache["default"] = {"value": "default"}
        print("Cache warmed up")

    @before_startup
    async def verify(self):
        assert self.connection is not None
        print("Cache verified")

    @before_shutdown
    async def cleanup(self):
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
    service = Cache()
    await service.configure()
    await service.init()
    await service.startup()

    await service.set("key", "value")
    assert await service.get("key") == "value"

    await service.shutdown()
```

## 最佳实践

1. **单一职责**：每个服务应该只负责一件事
2. **无状态设计**：尽量使服务无状态，或明确管理状态
3. **依赖最小化**：只声明真正需要的依赖
4. **类型注解**：使用类型注解声明依赖，获得 IDE 支持和更好的可读性
5. **测试覆盖**：为每个服务编写单元测试
6. **命名简洁**：类名尽量简短（如 `Database` 而非 `DatabaseService`），框架会自动追加 `Service` 后缀
