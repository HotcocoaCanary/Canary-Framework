# 依赖注入

Canary 框架具有内置的依赖注入（DI）系统，可自动管理服务依赖项。

## 工作原理

1. **声明依赖项**：指定服务依赖的服务
2. **注册服务**：服务在注册表中注册
3. **拓扑排序**：服务按依赖顺序排序
4. **实例化和注入**：服务被实例化并注入依赖项

## 声明依赖项

使用 `deps` 参数声明依赖项：

```python
@service(name="database")
class DatabaseService:
    pass

@service(name="cache")
class CacheService:
    pass

@service(name="user_repository", deps=[DatabaseService, CacheService])
class UserRepository:
    # DatabaseService 可用作 self.database_service
    # CacheService 可用作 self.cache_service
    pass
```

## 注入命名

依赖项使用 snake_case 命名作为属性注入：

| 类名 | 属性名 |
|------|--------|
| `DatabaseService` | `self.database_service` |
| `UserRepository` | `self.user_repository` |
| `APIRouter` | `self.api_router` |

## 依赖图

框架构建依赖图并确保服务按正确顺序初始化：

```python
@service(name="a")
class A:
    pass

@service(name="b", deps=[A])
class B:
    pass

@service(name="c", deps=[B])
class C:
    pass

# 启动顺序：A → B → C
```

## 循环依赖

框架检测并报告循环依赖：

```python
# ❌ 这将抛出 CircularDependencyError
@service(name="a", deps=["b"])
class A:
    pass

@service(name="b", deps=["a"])
class B:
    pass
```

## 共享实例

服务在其模块中是单例 - 只创建和共享一个实例：

```python
@service(name="database")
class DatabaseService:
    def __init__(self):
        print("DatabaseService created")  # 只打印一次

@service(name="service1", deps=[DatabaseService])
class Service1:
    pass

@service(name="service2", deps=[DatabaseService])
class Service2:
    pass

@module(name="app", services=[DatabaseService, Service1, Service2])
class AppModule:
    pass

# Service1 和 Service2 都获得同一个 DatabaseService 实例
```

## 父注册表

模块可以具有父注册表，允许服务在模块之间共享：

```python
@service(name="shared_db")
class SharedDatabase:
    pass

@service(name="auth_service", deps=[SharedDatabase])
class AuthService:
    pass

@service(name="product_service", deps=[SharedDatabase])
class ProductService:
    pass

@module(name="auth", services=[AuthService])
class AuthModule:
    pass

@module(name="products", services=[ProductService])
class ProductsModule:
    pass

@module(name="app", services=[SharedDatabase, AuthModule, ProductsModule])
class AppModule:
    pass

# AuthService 和 ProductService 共享同一个 SharedDatabase 实例
```

## 手动注入

如果需要，您可以手动注入依赖项：

```python
from canary_framework.engine.registry import Registry
from canary_framework.engine.injector import inject_deps

# 创建注册表
registry = Registry()
registry.register(MyService)
registry.register(MyDependency)

# 创建实例
for entry in registry:
    entry.instance = entry.cls()

# 注入依赖项
for entry in registry:
    inject_deps(entry.instance, entry, registry)
```

## 服务注册表

`Registry` 类管理服务注册和查找：

```python
from canary_framework.engine.registry import Registry

registry = Registry()

# 注册服务
registry.register(MyService)

# 按名称查找
entry = registry.get_by_name("my_service")

# 按类查找
entry = registry.get_by_class(MyService)

# 检查是否注册
if MyService in registry:
    pass

# 获取所有服务
for entry in registry:
    print(entry.name)
```

## 服务条目

注册表中的每个服务都由 `ServiceEntry` 表示：

```python
@dataclass
class ServiceEntry:
    cls: type              # 服务类
    name: str              # 服务名称
    instance: object       # 服务实例（配置前为 None）
    deps: List[type]       # 依赖项
    dep_names: List[str]   # 依赖项名称
```

## 拓扑排序

框架使用 Kahn 算法进行拓扑排序：

```python
from canary_framework.engine.injector import topological_sort

# 获取启动顺序
order = topological_sort(registry)
# 返回：["a", "b", "c"]
```

## 完整 DI 示例

```python
from canary_framework import module, service

# 第 1 层：基础设施
@service(name="database")
class DatabaseService:
    async def query(self, sql):
        return f"Query: {sql}"

@service(name="cache")
class CacheService:
    async def get(self, key):
        return None
    
    async def set(self, key, value):
        pass

# 第 2 层：仓库
@service(name="user_repo", deps=[DatabaseService, CacheService])
class UserRepository:
    async def get_user(self, user_id):
        cached = await self.cache_service.get(f"user:{user_id}")
        if cached:
            return cached
        
        user = await self.database_service.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache_service.set(f"user:{user_id}", user)
        return user

# 第 3 层：服务
@service(name="user_service", deps=[UserRepository])
class UserService:
    async def get_profile(self, user_id):
        user = await self.user_repo.get_user(user_id)
        return {"profile": user}

# 第 4 层：组合
@module(name="app", services=[DatabaseService, CacheService, UserRepository, UserService])
class AppModule:
    pass
```

## 设计原则

1. **显式依赖项**：依赖项声明清晰
2. **构造函数注入**：没有魔法，依赖项设置为属性
3. **拓扑顺序**：服务以正确顺序启动
4. **单实例**：服务在其范围内是单例
5. **错误检测**：循环依赖早期捕获
