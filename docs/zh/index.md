# Canary Framework

Canary Framework 是一个轻量级、装饰器驱动的 Python 异步服务框架，专为构建模块化、可维护和可测试的应用程序而设计。

## 核心特性

- **装饰器驱动**：使用简洁的装饰器定义服务、模块和路由 — 无需样板代码
- **注解驱动依赖注入**：通过 Python 类型注解声明依赖 — 无需 `deps` 列表
- **自动命名**：服务、模块和路由的名称从类名自动派生
- **生命周期管理**：完整的服务和模块生命周期钩子
- **ASGI 兼容**：基于 Starlette 构建，提供高性能异步 Web 应用
- **模块化架构**：通过可重用的模块组合您的应用
- **OpenAPI 支持**：自动生成 Swagger UI 和 ReDoc 文档

## 安装

```bash
pip install canary-framework
```

## 快速开始

以下是一个最简示例，帮助您快速上手：

```python
from canary_framework import service, module, config
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.common.config import CanaryConfig

@service()
class Api(ServiceBase):
    router = Router(prefix="/api")

    @router.get("/hello")
    async def hello(self):
        return {"message": "Hello, Canary!"}

    @router.post("/echo")
    async def echo(self, body: dict):
        return {"echo": body}

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8000

@module(services=[AppConfig, Api])
class App(ModuleBase):
    config: AppConfig

async def setup():
    app = App()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn
    app = asyncio.run(setup())
    uvicorn.run(app, host="0.0.0.0", port=8000, lifespan="on")
```

## OpenAPI 文档

启动应用后，可以访问以下端点：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`
- **OpenAPI JSON**：`http://localhost:8000/openapi.json`

## 核心概念

### 服务 (Service)

服务是应用的构建块，封装业务逻辑：

```python
from canary_framework import service, after_init, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    db_url: str = "sqlite:///app.db"

    @after_init
    async def connect(self):
        print("Database connected")
```

### 模块 (Module)

模块是组织和组合服务的容器：

```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

@module(services=[Database, Api])
class App(ModuleBase):
    pass
```

### 路由 (Router)

路由通过 `Router` 类属性定义，使用 `@router.get()` / `@router.post()` 方法装饰器。参数自动绑定，自动生成 OpenAPI 3.0.3 文档。

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Posts(ServiceBase):
    db: Database
    router = Router(prefix="/api/posts", tags=["Posts"])

    @router.get("/")
    async def list_posts(self, page: int = 1, limit: int = 10):
        return await self.db.query(f"SELECT * FROM posts LIMIT {limit} OFFSET {(page-1)*limit}")

    @router.get("/{post_id}")
    async def get_post(self, post_id: int):
        return await self.db.query(f"SELECT * FROM posts WHERE id={post_id}")

    @router.post("/", request_model=PostCreate)
    async def create_post(self, body: PostCreate):
        return await self.db.create_post(body), 201
```

### 依赖注入

通过类型注解声明依赖 — 框架自动解析并注入：

```python
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class UserRepo(ServiceBase):
    db: Database  # 框架自动注入为 self.db

    async def get_user(self, user_id):
        return await self.db.query(...)
```

## 下一步

- [快速入门](./quickstart.md) - 更全面的入门指南
- [服务](./services.md) - 了解服务定义和生命周期
- [模块](./modules.md) - 理解模块组合
- [Web 路由](./web.md) - 用路由构建 Web API
- [依赖注入](./dependency-injection.md) - 掌握注解驱动的 DI 系统
- [生命周期](./lifecycle.md) - 控制服务初始化和清理
- [核心概念](./core.md) - 深入了解框架内部机制
- [API 参考](./api-reference.md) - 完整的 API 文档

## 设计原则

1. **装饰器驱动** — 代码即配置
2. **异步优先** — 基于 async/await 构建
3. **注解驱动依赖注入** — 通过类型注解声明依赖
4. **自动命名** — 名称从类名派生，无需手动指定字符串
5. **可组合性** — 通过模块构建复杂系统
