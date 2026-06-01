# 模块

模块是组织和组合服务的容器。它们管理其子服务的生命周期，并提供一种层次化地构建应用程序的方式。

## 定义模块

使用 `@module` 装饰器定义模块：

```python
from canary_framework import module

@module(name="auth_module", services=[...])
class AuthModule:
    pass
```

### 模块参数

- `name`：（必需）模块的唯一标识符
- `services`：（可选）此模块包含的服务或模块类列表
- `deps`：（可选）此模块依赖的服务或模块列表

## 模块组合

模块可以包含服务和其他模块，创建层次化结构：

```python
from canary_framework import module, service, router

# 核心服务
@service(name="database")
class DatabaseService:
    pass

@service(name="cache")
class CacheService:
    pass

# 认证模块
@service(name="auth_service", deps=[DatabaseService])
class AuthService:
    pass

@router(name="auth_api", prefix="/auth", deps=[AuthService])
class AuthRouter:
    pass

@module(name="auth", services=[AuthService, AuthRouter])
class AuthModule:
    pass

# 文章模块
@service(name="posts_service", deps=[DatabaseService, CacheService])
class PostsService:
    pass

@router(name="posts_api", prefix="/posts", deps=[PostsService])
class PostsRouter:
    pass

@module(name="posts", services=[PostsService, PostsRouter])
class PostsModule:
    pass

# 主应用模块
@module(
    name="app",
    services=[
        DatabaseService,
        CacheService,
        AuthModule,
        PostsModule
    ]
)
class AppModule:
    pass
```

## 模块生命周期

模块协调其子服务的生命周期。当调用模块的生命周期方法时，它们按拓扑顺序传播到所有子服务。

```python
app = AppModule()

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

## 模块作为 ASGI 应用

模块可以直接用作 ASGI 应用。它自动挂载所有子路由：

```python
import uvicorn

# 将模块作为 ASGI 应用运行
uvicorn.run("main:AppModule", host="0.0.0.0", port=8000)
```

模块将：
1. 从其服务中收集所有路由
2. 将它们挂载在基于其服务名称的路径上
3. 处理 ASGI 请求

## 模块基类

当您用 `@module` 装饰一个类时，它会自动继承自 `ModuleBase`，该类提供：

- `config` 属性：访问配置
- `configure(config)` 方法：配置模块和所有服务
- `init()` 方法：初始化模块和所有服务
- `startup()` 方法：启动模块和所有服务
- `shutdown()` 方法：关闭模块和所有服务
- `asgi_app` 属性：访问 ASGI 应用

## 依赖共享

模块中的服务共享依赖项。如果多个服务依赖于同一个服务，则只创建并共享一个实例：

```python
@service(name="database")
class DatabaseService:
    pass

@service(name="service_a", deps=[DatabaseService])
class ServiceA:
    pass

@service(name="service_b", deps=[DatabaseService])
class ServiceB:
    pass

@module(name="app", services=[DatabaseService, ServiceA, ServiceB])
class AppModule:
    pass

# ServiceA 和 ServiceB 都将接收同一个 DatabaseService 实例
```

## 完整示例

```python
from canary_framework import module, service, router, get

# 服务
@service(name="db")
class Database:
    pass

@service(name="user_repo", deps=[Database])
class UserRepository:
    pass

@service(name="user_service", deps=[UserRepository])
class UserService:
    pass

# 路由
@router(name="users", prefix="/api/users", deps=[UserService])
class UsersRouter:
    @get("/")
    async def list_users(self, request):
        return {"users": []}

# 模块
@module(name="users_module", services=[UserRepository, UserService, UsersRouter])
class UsersModule:
    pass

@module(name="app", services=[Database, UsersModule])
class App:
    pass
```

## 最佳实践

1. **分层架构**：按功能划分模块（如 auth、users、posts）
2. **单一职责**：每个模块专注于一个功能领域
3. **模块组合**：通过组合小模块构建大型应用
4. **配置隔离**：为每个模块提供独立的配置空间
5. **测试隔离**：每个模块可以独立测试
