# 模块

模块是组织和组合服务的容器。它们管理其子服务的生命周期，并提供一种层次化地构建应用程序的方式。

## 定义模块

使用 `@module` 装饰器定义模块。类必须显式继承 `ModuleBase`。只需提供 `services` 参数，模块名称自动生成为 `类名 + "Module"`：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[...])
class Auth(ModuleBase):
    pass
```

### 模块参数

- `services`：（可选）此模块包含的服务或模块类列表。

> 注意：旧的 `name`、`deps` 和 `config` 参数已移除。名称自动生成，依赖通过类型注解声明。

### 自动命名

模块名称自动生成为 `类名 + "Module"`：

| 类名 | 自动生成的模块名 |
|------|-----------------|
| `Auth` | `AuthModule` |
| `BlogApp` | `BlogAppModule` |
| `App` | `AppModule` |

## 模块组合

模块可以包含服务和其他模块，创建层次化结构：

```python
from canary_framework import module, service, router
from canary_framework.core import ServiceBase, ModuleBase, RouterBase

# 核心服务
@service()
class Database(ServiceBase):
    pass

@service()
class Cache(ServiceBase):
    pass

# 认证模块
@service()
class AuthService(ServiceBase):
    db: DatabaseService

@router(prefix="/auth")
class AuthRouter(RouterBase):
    auth_svc: AuthService

@module(services=[AuthService, AuthRouter])
class Auth(ModuleBase):
    pass

# 文章模块
@service()
class PostsService(ServiceBase):
    db: DatabaseService
    cache: CacheService

@router(prefix="/posts")
class PostsRouter(RouterBase):
    svc: PostsService

@module(services=[PostsService, PostsRouter])
class Posts(ModuleBase):
    pass

# 主应用模块
@module(services=[DatabaseService, CacheService, AuthModule, PostsModule])
class App(ModuleBase):
    pass
```

## 模块生命周期

模块协调其子服务的生命周期。当调用模块的生命周期方法时，它们按拓扑顺序传播到所有子服务。

```python
app = App()

# 1. 配置阶段：按依赖顺序配置所有服务
await app.configure(config)

# 2. 初始化阶段：初始化所有服务
await app.init()

# 3. 启动阶段：启动所有服务
await app.startup()

# ... 应用运行 ...

# 4. 关闭阶段：按相反顺序关闭所有服务
await app.shutdown()
```

### 配置阶段的详细流程

调用 `module.configure(config_instance)` 时：

1. 收集模块的 `services` 列表中所有服务类
2. 递归注册：对每个服务，调用 `_register_entry_with_deps()` 将其及其依赖注册到 Registry
3. 拓扑排序：`topological_sort(registry)` 使用 `resolve_deps()` 构建依赖图
4. 按拓扑顺序实例化所有服务
5. 按拓扑顺序注入依赖：通过 `resolve_deps()` 读取类型注解，用 `setattr` 注入
6. 模块通过 `setattr(self, entry.cls.__name__, inst)` 挂载子服务（用原始类名）
7. 按拓扑顺序调用每个服务的 `configure(config_instance)`
8. 调用模块自身的 `@after_config` 钩子

## 模块作为 ASGI 应用

模块可以直接用作 ASGI 应用。它自动挂载所有子路由：

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080

async def setup():
    cfg = AppConfig()
    app = App()
    await app.configure(cfg)
    await app.init()
    return app, cfg

import asyncio
import uvicorn

app, cfg = asyncio.run(setup())
uvicorn.run(app, host=cfg.host, port=cfg.port, lifespan="on")
```

模块将：
1. 从其服务中收集所有路由
2. 将它们挂载在基于其服务名称的路径上
3. 处理 ASGI 请求

## 模块基类

使用 `@module` 装饰的类必须显式继承自 `ModuleBase`，该类提供：

- `config` 属性：访问配置
- `configure(config_instance=None)` 方法：配置模块和所有服务
- `init()` 方法：初始化模块和所有服务
- `startup()` 方法：启动模块和所有服务
- `shutdown()` 方法：关闭模块和所有服务
- `asgi_app` 属性：访问 ASGI 应用
- `__call__(scope, receive, send)`：ASGI 应用入口点（继承自 ServiceBase）

## 依赖共享

模块中的服务共享依赖项。如果多个服务依赖于同一个服务，则只创建并共享一个实例：

```python
from canary_framework import service, module
from canary_framework.core import ServiceBase, ModuleBase

@service()
class Database(ServiceBase):
    pass

@service()
class ServiceA(ServiceBase):
    db: DatabaseService

@service()
class ServiceB(ServiceBase):
    db: DatabaseService

@module(services=[DatabaseService, ServiceA, ServiceB])
class App(ModuleBase):
    pass

# ServiceA 和 ServiceB 都将接收同一个 Database 实例
```

## 访问子服务

配置完成后，模块的子服务通过**原始类名**（PascalCase）可访问：

```python
@module(services=[DatabaseService, AuthService, PostsRouter])
class App(ModuleBase):
    pass

app = App()
await app.configure()

# 通过原始类名访问
app.Database          # Database 实例
app.AuthService       # Auth 实例
app.PostsRouter       # Posts 实例

app.AuthService.db    # Auth 的 Database 依赖
```

## 完整示例

```python
from canary_framework import module, service, router, get
from canary_framework.core import ServiceBase, ModuleBase, RouterBase

# 服务
@service()
class Database(ServiceBase):
    pass

@service()
class UserRepository(ServiceBase):
    db: DatabaseService

@service()
class UserService(ServiceBase):
    repo: UserRepositoryService

# 路由
@router(prefix="/api/users")
class UsersRouter(RouterBase):
    svc: UserService

    @get("/")
    async def list_users(self):
        return {"users": []}

# 模块
@module(services=[UserRepositoryService, UserService, UsersRouter])
class Users(ModuleBase):
    pass

@module(services=[DatabaseService, UsersModule])
class App(ModuleBase):
    pass
```

## 最佳实践

1. **分层架构**：按功能划分模块（如 auth、users、posts）
2. **单一职责**：每个模块专注于一个功能领域
3. **模块组合**：通过组合小模块构建大型应用
4. **配置隔离**：为每个模块提供独立的配置空间
5. **测试隔离**：每个模块可以独立测试
6. **简洁命名**：类名尽量简短（如 `App` 而非 `AppModule`），框架自动追加后缀
