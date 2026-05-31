# Canary 框架

Canary 框架是一个轻量级、装饰器驱动的 Python 异步服务框架，专为构建模块化、可维护和可测试的应用程序而设计。

## 核心特性

- **装饰器驱动**：使用简单的装饰器来定义服务、模块和路由
- **依赖注入**：内置的 DI 容器，自动解析依赖
- **生命周期管理**：完整的服务和模块生命周期钩子
- **ASGI 兼容**：基于 Starlette 构建，提供高性能的异步 Web 应用
- **模块化架构**：通过可重用的模块组合您的应用

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

## 下一步

- [快速入门](./quickstart.md) - 更全面的指南
- [服务](./services.md) - 了解服务定义和生命周期
- [模块](./modules.md) - 理解模块组合
- [Web 路由](./web.md) - 用路由构建 Web API
- [依赖注入](./dependency-injection.md) - 掌握 DI 系统
- [生命周期](./lifecycle.md) - 控制服务初始化和清理
- [核心概念](./core.md) - 深入了解框架内部
- [API 参考](./api-reference.md) - 完整的 API 文档
