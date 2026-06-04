# 模块

模块是组织和组合服务的容器。它们管理其子服务的生命周期，并提供一种层次化地构建应用程序的方式。

## 定义模块

使用 `@module()` 装饰器定义模块：

```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

@module(services=[Database, UserRepo, AuthApi])
class Auth(ModuleBase):
    pass
```

- `@module(services=[...])` — 仅需要 `services` 参数
- 名称从类名自动生成（`ClassName` + `"Module"`）
- 模块自动命名为 `AuthModule`

## 模块组合

模块可以包含服务和其他模块，创建层次化结构：

```python
from canary_framework import module, service, router
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase

# 核心服务
@service()
class Database(ServiceBase):
    pass

@service()
class Cache(ServiceBase):
    pass

# Auth 模块
@service()
class AuthService(ServiceBase):
    db: Database

@router(prefix="/auth")
class AuthApi(RouterBase):
    auth: AuthService

@module(services=[AuthService, AuthApi])
class Auth(ModuleBase):
    pass

# Posts 模块
@service()
class PostsService(ServiceBase):
    db: Database
    cache: Cache

@router(prefix="/posts")
class PostsApi(RouterBase):
    posts: PostsService

@module(services=[PostsService, PostsApi])
class Posts(ModuleBase):
    pass

# 主应用模块
@module(services=[Database, Cache, Auth, Posts])
class App(ModuleBase):
    pass
```

## 模块子服务访问

子服务和子模块通过其类名直接在模块实例上访问：

```python
app = App()
await app.configure(config)

# 通过类名访问子服务（非 snake_case）
app.Database    # Database 服务实例
app.Cache       # Cache 服务实例
app.Auth        # Auth 子模块实例
app.Posts       # Posts 子模块实例
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

# 4. 关闭阶段：按逆序关闭所有服务
await app.shutdown()
```

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
2. 根据其 prefix 将它们挂载在路径上
3. 处理 ASGI 请求

## 模块基类

使用 `@module()` 装饰的类必须显式继承 `ModuleBase`，该类提供：

- `config` 属性：访问配置
- `configure(config_instance=None)` 方法：配置模块和所有服务
- `init()` 方法：初始化模块和所有服务
- `startup()` 方法：启动模块和所有服务
- `shutdown()` 方法：关闭模块和所有服务
- `asgi_app` 属性：访问 ASGI 应用

## 依赖共享

模块中的服务共享依赖项。如果多个服务依赖于同一个服务，则只创建并共享一个实例：

```python
@service()
class Database(ServiceBase):
    pass

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

## 完整示例

```python
from canary_framework import module, service, router, get
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase

# 服务
@service()
class Database(ServiceBase):
    async def query(self, sql):
        pass

@service()
class UserRepo(ServiceBase):
    db: Database

@service()
class UserService(ServiceBase):
    repo: UserRepo

# 路由
@router(prefix="/api/users")
class Users(RouterBase):
    user: UserService

    @get("/")
    async def list_users(self):
        return {"users": []}

# 模块
@module(services=[UserRepo, UserService, Users])
class UsersModule(ModuleBase):
    pass

@module(services=[Database, UsersModule])
class App(ModuleBase):
    pass
```

## 最佳实践

1. **分层架构**：按功能组织模块（如 auth、users、posts）
2. **单一职责**：每个模块专注于一个功能领域
3. **模块组合**：通过组合小模块构建大型应用
4. **配置隔离**：为每个模块提供独立的配置空间
5. **测试隔离**：每个模块可以独立测试
6. **使用有描述性的注解名称**：`db`、`repo`、`service` — 而非 `d1`、`d2`
