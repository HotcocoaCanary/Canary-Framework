# 依赖注入

Canary 框架具有内置的依赖注入（DI）系统，通过 Python 类型注解自动管理服务依赖。

## 工作原理

1. **声明依赖**：通过类型注解在类体中声明依赖
2. **解析依赖**：`resolve_deps(cls)` 读取类型注解并过滤 CF_SERVICE_MARKER
3. **注册服务**：服务及其依赖递归注册到注册表
4. **拓扑排序**：`topological_sort(registry)` 使用 `resolve_deps()` 构建依赖图
5. **实例化和注入**：按拓扑顺序实例化，通过 `setattr` 按注解键名注入依赖

## 声明依赖

通过类型注解声明依赖（不再使用 `deps` 参数）：

```python
@service()
class Database:
    pass

@service()
class Cache:
    pass

@service()
class UserRepository:
    db: DatabaseService
    cache: CacheService

    # db 可通过 self.db 访问
    # cache 可通过 self.cache 访问
    pass
```

## 注入命名

与旧版不同，注入的属性名**完全由您的注解键名控制**，而非框架自动生成 snake_case：

| 注解 | 访问方式 |
|------|---------|
| `db: DatabaseService` | `self.db` |
| `cache: CacheService` | `self.cache` |
| `my_repo: UserRepositoryService` | `self.my_repo` |
| `auth: AuthService` | `self.auth` |

这意味着您可以自由选择任何变量名。

## 依赖图

框架通过 `resolve_deps()` 读取类型注解构建依赖图，并确保服务按正确顺序初始化：

```python
@service()
class A:
    pass

@service()
class B:
    a: AService

@service()
class C:
    b: BService

# 启动顺序：A → B → C
```

## 循环依赖

框架检测并报告循环依赖：

```python
# ❌ 这将抛出 CircularDependencyError
@service()
class A:
    b: "BService"

@service()
class B:
    a: "AService"
```

## 共享实例

服务在其模块中是单例 — 只创建和共享一个实例：

```python
@service()
class Database:
    def __init__(self):
        print("Database created")  # 只打印一次

@service()
class Service1:
    db: DatabaseService

@service()
class Service2:
    db: DatabaseService

@module(services=[DatabaseService, Service1, Service2])
class App:
    pass

# Service1 和 Service2 都获得同一个 Database 实例
```

## 父注册表

模块可以具有父注册表，允许服务在模块之间共享：

```python
@service()
class SharedDatabase:
    pass

@service()
class AuthService:
    db: SharedDatabaseService

@service()
class ProductService:
    db: SharedDatabaseService

@module(services=[AuthService])
class AuthModule:
    pass

@module(services=[ProductService])
class ProductsModule:
    pass

@module(services=[SharedDatabaseService, AuthModule, ProductsModule])
class App:
    pass

# AuthService 和 ProductService 共享同一个 SharedDatabase 实例
```

## DI 详细流程

```
1. 收集模块的 services 列表中的所有服务类
   ↓
2. 递归注册：对每个服务，调用 _register_entry_with_deps()
   ├─ 检查是否已在注册表中（幂等）
   ├─ 注册到 Registry
   └─ 通过 resolve_deps(cls) 读取类型注解
      └─ 递归注册所有依赖
   ↓
3. topological_sort(registry)：构建依赖图并拓扑排序
   ├─ 遍历所有条目，通过 resolve_deps() 获取依赖
   ├─ 构建入度表和邻接表
   └─ 使用 Kahn 算法排序
   ↓
4. 按拓扑顺序实例化所有服务
   ↓
5. 按拓扑顺序注入依赖：
   for attr_name, dep_cls in resolve_deps(type(inst)).items():
       setattr(inst, attr_name, registry.get_by_class(dep_cls).instance)
   ↓
6. 模块通过 setattr(self, entry.cls.__name__, inst) 挂载子服务
   ↓
7. 运行生命周期：configure → init → startup → shutdown
```

## resolve_deps 函数

`resolve_deps(cls)` 是 DI 系统的核心：

```python
from canary_framework.common.markers import resolve_deps

def resolve_deps(cls: type) -> dict[str, type]:
    """从类的类型注解中解析依赖映射。

    返回 {属性名: 依赖类型}，只包含被 @service/@module/@router 装饰的类型。
    """
    from typing import get_type_hints
    hints = get_type_hints(cls)
    return {
        name: tp
        for name, tp in hints.items()
        if isinstance(tp, type) and hasattr(tp, CF_SERVICE_MARKER)
    }
```

## 模块子服务访问

模块在配置完成后，其子服务通过原始类名（PascalCase）作为属性可访问：

```python
@module(services=[DatabaseService, AuthService])
class App:
    pass

app = App()
await app.configure()

# 通过原始类名访问子服务
app.Database          # Database 服务实例
app.AuthService       # Auth 服务实例

# 而不是 snake_case 命名（这已不再适用）
# app.database_service  # ❌ 不存在
```

## 完整 DI 示例

```python
from canary_framework import module, service

# 第 1 层：基础设施
@service()
class Database:
    async def query(self, sql):
        return f"Query: {sql}"

@service()
class Cache:
    async def get(self, key):
        return None

    async def set(self, key, value):
        pass

# 第 2 层：仓库
@service()
class UserRepository:
    db: DatabaseService
    cache: CacheService

    async def get_user(self, user_id):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached

        user = await self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache.set(f"user:{user_id}", user)
        return user

# 第 3 层：服务
@service()
class UserService:
    repo: UserRepositoryService

    async def get_profile(self, user_id):
        user = await self.repo.get_user(user_id)
        return {"profile": user}

# 第 4 层：组合
@module(services=[DatabaseService, CacheService, UserRepositoryService, UserService])
class App:
    pass
```

## 设计原则

1. **注解驱动依赖**：依赖通过类型注解声明，清晰直观
2. **自动解析**：`resolve_deps()` 自动识别框架类型
3. **拓扑顺序**：服务以正确的依赖顺序启动
4. **单实例**：服务在其范围内是单例
5. **错误检测**：循环依赖在启动时早期捕获
