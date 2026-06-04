# 依赖注入

Canary Framework 具有内置的、注解驱动的依赖注入（DI）系统，自动管理服务依赖。

## 工作原理

1. **声明依赖**：在服务类上使用 Python 类型注解
2. **解析**：`resolve_deps(cls)` 读取注解并按 `CF_SERVICE_MARKER` 过滤
3. **注册**：服务及其依赖递归注册
4. **拓扑排序**：`topological_sort(registry)` 构建依赖图并确定实例化顺序
5. **实例化和注入**：按顺序实例化服务；依赖通过 `setattr` 使用注解键名设置

## 声明依赖

在类体上使用类型注解声明依赖：

```python
@service()
class Database(ServiceBase):
    pass

@service()
class Cache(ServiceBase):
    pass

@service()
class UserRepository(ServiceBase):
    db: Database    # 自动注入为 self.db
    cache: Cache    # 自动注入为 self.cache

    async def get_user(self, user_id):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        user = await self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache.set(f"user:{user_id}", user)
        return user
```

注解键名成为实例上的属性名：

| 注解 | 注入为 |
|------------|-------------|
| `db: Database` | `self.db` |
| `cache: Cache` | `self.cache` |
| `auth: AuthService` | `self.auth` |

**您选择属性名** — 只需按照您喜欢的方式命名注解字段。

## 依赖图

框架构建依赖图并确保服务按正确顺序初始化：

```python
@service()
class A(ServiceBase):
    pass

@service()
class B(ServiceBase):
    a: A  # 依赖 A

@service()
class C(ServiceBase):
    b: B  # 依赖 B

# 拓扑排序确定顺序：A → B → C
```

## DI 执行流程

```
1. resolve_deps(cls) 读取类上的注解
   ↓
2. 过滤注解：仅保留带有 CF_SERVICE_MARKER 的类型
   ↓
3. 递归注册每个依赖到注册表
   ↓
4. topological_sort(registry) 构建依赖图
   ↓
5. 按拓扑顺序实例化服务
   ↓
6. 对每个服务：setattr(instance, attr_name, resolved_dep_instance)
   ↓
7. 运行生命周期钩子
```

## 循环依赖

框架检测并报告循环依赖：

```python
# ❌ 这将抛出 CircularDependencyError
@service()
class A(ServiceBase):
    b: B

@service()
class B(ServiceBase):
    a: A
```

## 共享实例

服务在其模块中是单例 — 只创建并共享一个实例：

```python
@service()
class Database(ServiceBase):
    def __init__(self):
        print("Database created")  # 只打印一次

@service()
class ServiceA(ServiceBase):
    db: Database

@service()
class ServiceB(ServiceBase):
    db: Database

@module(services=[Database, ServiceA, ServiceB])
class App(ModuleBase):
    pass

# ServiceA 和 ServiceB 都接收到同一个 Database 实例
```

## 父注册表

模块可以具有父注册表，允许服务在模块之间共享：

```python
@service()
class SharedDatabase(ServiceBase):
    pass

@service()
class AuthService(ServiceBase):
    db: SharedDatabase

@service()
class ProductService(ServiceBase):
    db: SharedDatabase

@module(services=[AuthService])
class AuthModule(ModuleBase):
    pass

@module(services=[ProductService])
class ProductsModule(ModuleBase):
    pass

@module(services=[SharedDatabase, AuthModule, ProductsModule])
class App(ModuleBase):
    pass

# AuthService 和 ProductService 共享同一个 SharedDatabase 实例
```

## 模块子服务访问

模块子服务通过类名作为属性访问：

```python
@module(services=[Database, Auth])
class App(ModuleBase):
    pass

app = App()
await app.configure(config)  # config: CanaryConfig | None

# 通过类名直接访问子服务
app.Database    # Database 服务实例
app.Auth        # Auth 服务实例
```

## 手动注入

如果需要，您可以手动解析依赖：

```python
from canary_framework.engine.registry import Registry
from canary_framework.engine.injector import topological_sort, resolve_deps

registry = Registry()
registry.register(MyService)

# resolve_deps 读取 MyService 上的注解以查找依赖
# topological_sort 使用 resolve_deps() 构建完整图
for entry in topological_sort(registry):
    entry.instance = entry.cls()
    # 使用注解键名通过 setattr 设置依赖
```

## 服务注册表

`Registry` 类管理服务注册和查找：

```python
from canary_framework.engine.registry import Registry

registry = Registry()

registry.register(MyService)

entry = registry.get_by_class(MyService)

if MyService in registry:
    pass

for entry in registry:
    print(entry.cls)
```

## ServiceEntry

注册表中的每个服务由 `ServiceEntry` 表示：

```python
@dataclass
class ServiceEntry:
    cls: type                  # 服务类
    name: str                  # 自动生成的服务名称
    instance: object = None    # 服务实例（配置前为 None）
```

## 拓扑排序

框架使用 Kahn 算法进行拓扑排序，由 `resolve_deps()` 驱动：

```python
from canary_framework.engine.injector import topological_sort

order = topological_sort(registry)
# 返回按依赖顺序排列的条目
```

## 完整 DI 示例

```python
from canary_framework import module, service
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase

# 第 1 层：基础设施
@service()
class Database(ServiceBase):
    async def query(self, sql):
        return f"Query: {sql}"

@service()
class Cache(ServiceBase):
    async def get(self, key):
        return None

    async def set(self, key, value):
        pass

# 第 2 层：仓库
@service()
class UserRepo(ServiceBase):
    db: Database
    cache: Cache

    async def get_user(self, user_id):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        user = await self.db.query(f"SELECT * FROM users WHERE id={user_id}")
        await self.cache.set(f"user:{user_id}", user)
        return user

# 第 3 层：服务
@service()
class UserService(ServiceBase):
    repo: UserRepo

    async def get_profile(self, user_id):
        user = await self.repo.get_user(user_id)
        return {"profile": user}

# 第 4 层：组合
@module(services=[Database, Cache, UserRepo, UserService])
class App(ModuleBase):
    pass
```

## 设计原则

1. **注解驱动**：通过 Python 类型提示声明依赖 — 无需单独的 `deps` 列表
2. **灵活命名**：您通过注解键控制属性名
3. **自动解析**：`resolve_deps()` 通过读取注解发现依赖
4. **拓扑顺序**：服务以正确的依赖顺序启动
5. **单实例**：服务在其作用域内是单例
6. **错误检测**：循环依赖在早期被捕获
