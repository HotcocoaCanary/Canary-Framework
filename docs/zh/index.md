# Canary Framework

Canary Framework 是一个轻量级、装饰器驱动的 Python 异步服务框架，专为构建模块化、可维护和可测试的应用程序而设计。

## 核心特性

- **装饰器驱动**：使用简洁的装饰器定义服务、模块和路由
- **注解驱动依赖注入**：通过 Python 类型注解声明依赖，框架自动注入
- **自动命名**：服务/模块/路由的名称自动生成，无需手动指定
- **生命周期管理**：完整的服务和模块生命周期钩子
- **自动参数绑定**：路由处理器的路径参数、查询参数和请求体自动解析
- **ASGI 兼容**：基于 Starlette 构建，提供高性能的异步 Web 应用
- **模块化架构**：通过可重用的模块组合您的应用
- **OpenAPI 支持**：自动生成 Swagger UI 和 ReDoc 文档

## 安装

```bash
pip install canary-framework
```

## 快速开始

以下是一个简单的入门示例：

```python
from canary_framework import module, router, get, post, service
from canary_framework.core import ServiceBase, ModuleBase, RouterBase

@service()
class DatabaseService(ServiceBase):
    pass

@router(prefix="/api")
class ApiRouter(RouterBase):
    db: DatabaseService

    @get("/hello")
    async def hello(self):
        return {"message": "Hello, Canary!"}

    @post("/echo")
    async def echo(self, data: dict):
        return {"echo": data}

@module(services=[DatabaseService, ApiRouter])
class AppModule(ModuleBase):
    pass
```

运行应用：

```bash
uvicorn main:AppModule --reload
```

## OpenAPI 文档

启动应用后，可以访问以下端点：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## 核心概念

### 服务 (Service)

服务是应用的基本构建块，封装业务逻辑。`@service()` 无参数调用，类必须显式继承 `ServiceBase`。名称自动生成为 `ClassName + "Service"`：

```python
from canary_framework import service, after_config
from canary_framework.core import ServiceBase

@service()
class Database(ServiceBase):
    @after_config
    async def connect(self):
        print("Database connected")
```

### 模块 (Module)

模块组织和组合服务，使用 `services` 参数指定子服务。类必须显式继承 `ModuleBase`。名称自动生成为 `ClassName + "Module"`：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[DatabaseService, ApiRouter])
class App(ModuleBase):
    pass
```

### 路由 (Router)

路由处理 HTTP 请求，支持 `prefix` 和 `tags` 参数。类必须显式继承 `RouterBase`。名称自动生成为 `ClassName + "Router"`：

```python
from canary_framework import router, get
from canary_framework.core import RouterBase

@router(prefix="/users")
class UsersRouter(RouterBase):
    @get("/")
    async def list_users(self):
        return {"users": []}
```

### 依赖注入

依赖通过 Python 类型注解声明，框架自动注入：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class UserService(ServiceBase):
    db: DatabaseService

    async def get_user(self, user_id):
        return await self.db.query(...)
```

## 下一步

- [快速入门](./quickstart.md) - 更全面的指南
- [服务](./services.md) - 了解服务定义和生命周期
- [模块](./modules.md) - 理解模块组合
- [Web 路由](./web.md) - 用路由构建 Web API
- [依赖注入](./dependency-injection.md) - 掌握 DI 系统
- [生命周期](./lifecycle.md) - 控制服务初始化和清理
- [核心概念](./core.md) - 深入了解框架内部
- [API 参考](./api-reference.md) - 完整的 API 文档

## 设计原则

1. **装饰器驱动** — 代码即配置
2. **异步优先** — 基于 async/await
3. **注解驱动依赖** — 通过类型注解声明，清晰直观
4. **约定优于配置** — 自动命名，合理的默认值
5. **可组合性** — 通过模块构建复杂系统
