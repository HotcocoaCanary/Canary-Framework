# 服务

服务是 Canary Framework 应用程序的构建块。它们封装业务逻辑，可以组合在一起形成复杂的系统。

## 定义服务

使用 `@service()` 装饰器定义服务：

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class UserRepository(ServiceBase):
    def __init__(self):
        self.users = []

    async def get_all(self):
        return self.users

    async def add(self, user):
        self.users.append(user)
        return user
```

- 服务自动命名为 `ClassName` + `"Service"` — 例如 `UserRepository` → `UserRepositoryService`
- 名称从类名自动生成
- 要添加 HTTP 路由，请在类上定义 `router` 类属性并赋予一个 `Router` 实例（参见 [Web 路由](./web.md)）

## 声明依赖

依赖通过 Python 类型注解声明，而非 `deps` 列表：

```python
@service()
class Database(ServiceBase):
    pass

@service()
class UserRepo(ServiceBase):
    db: Database  # 通过注解声明 — 自动注入

    async def get_user(self, user_id):
        return await self.db.query(...)
```

- 注解由 `resolve_deps()` 解析 — 仅标记了 `CF_SERVICE_MARKER` 的类型被视为依赖
- 注入的实例设置在注解键名上（如 `self.db` 对应 `db: Database`）
- **您控制属性名** — 使用任何有效的 Python 标识符：`db`、`cache`、`repo` 等

## 服务生命周期

服务经历明确定义的生命周期：

1. **实例化**：创建服务实例
2. **初始化**：调用 `init()`；重写 `init()` 来建立连接和填充种子数据
3. **启动**：调用 `startup()`；之前运行 `@before_startup` 钩子
4. **关闭**：运行 `@before_shutdown` 钩子，然后调用 `shutdown()`

您可以使用生命周期装饰器介入这些阶段。有关详细信息，请参阅[生命周期](./lifecycle.md)文档。

## 服务基类

使用 `@service()` 装饰的类必须显式继承 `ServiceBase`，该类提供：

- `init()` 方法：初始化服务
- `startup()` 方法：启动服务
- `shutdown()` 方法：关闭服务

## 完整示例

```python
from canary_framework import service, before_startup, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Cache(ServiceBase):
    def __init__(self):
        self.store = {}
        self.connection = None

    async def init(self):
        await super().init()
        self.connection = "connected"
        print("Cache connected")
        self.store["default"] = {"value": "default"}
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
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value
```

## 服务命名

服务名称从类名自动派生：

| 类名 | 服务名称（自动） |
|------------|---------------------|
| `Database` | `DatabaseService` |
| `UserRepository` | `UserRepositoryService` |
| `Cache` | `CacheService` |

此名称在内部用于注册表查找。在大多数代码中，您通过类来引用服务。

## 测试服务

服务易于测试，因为它们是普通的 Python 类：

```python
import pytest

@pytest.mark.asyncio
async def test_cache():
    svc = Cache()
    await svc.init()
    await svc.startup()

    await svc.set("key", "value")
    assert await svc.get("key") == "value"

    await svc.shutdown()
```

## 最佳实践

1. **单一职责**：每个服务应该只做好一件事
2. **无状态设计**：优先使用无状态服务，或显式管理状态
3. **依赖最小化**：只声明真正需要的依赖
4. **类型注解**：使用类型提示清晰地声明依赖
5. **测试覆盖**：为每个服务编写单元测试
6. **有意义的注解名称**：为依赖属性选择有描述性的名称（如 `db` 而非 `d`）
