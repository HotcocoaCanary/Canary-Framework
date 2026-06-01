# Canary Framework

Canary Framework 是一个轻量级、装饰器驱动的 Python 异步服务框架，专为构建模块化、可维护和可测试的应用程序而设计。

## 核心特性

- **装饰器驱动**：使用简单的装饰器来定义服务、模块和路由
- **依赖注入**：内置的 DI 容器，自动解析依赖
- **生命周期管理**：完整的服务和模块生命周期钩子
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
from canary_framework import module, router, get, post

@router(name="api")
class ApiRouter:
    @get("/hello")
    async def hello(self, request):
        return {"message": "Hello, Canary!"}
    
    @post("/echo")
    async def echo(self, request):
        data = await request.json()
        return {"echo": data}

@module(name="app", services=[ApiRouter])
class AppModule:
    pass

# 使用 uvicorn 运行
# uvicorn main:AppModule --reload
```

## OpenAPI 文档

启动应用后，可以访问以下端点：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## 核心概念

### 服务 (Service)

服务是应用的基本构建块，封装业务逻辑：

```python
from canary_framework import service, after_config

@service(name="database")
class DatabaseService:
    @after_config
    async def connect(self):
        print("Database connected")
```

### 模块 (Module)

模块是组织和组合服务的容器：

```python
from canary_framework import module

@module(name="app", services=[DatabaseService, ApiRouter])
class AppModule:
    pass
```

### 路由 (Router)

路由处理 HTTP 请求：

```python
from canary_framework import router, get

@router(name="users", prefix="/users")
class UsersRouter:
    @get("/")
    async def list_users(self, request):
        return {"users": []}
```

### 依赖注入

服务可以声明依赖，框架自动注入：

```python
@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        return await self.database_service.query(...)
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

1. **装饰器驱动** - 代码即配置
2. **异步优先** - 基于 async/await
3. **显式依赖** - 清晰的依赖声明
4. **约定优于配置** - 合理的默认值
5. **可组合性** - 通过模块构建复杂系统