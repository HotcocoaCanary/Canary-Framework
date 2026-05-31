<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">Lightweight Python Async Service Framework — Decorator-Driven, Zero Boilerplate</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/canary-framework/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
</p>

---

Canary Framework 是一个**装饰器驱动**的异步服务框架。核心哲学：**服务是最小单元，模块组合服务，模块本身也是服务。**

## 核心特性

- **装饰器驱动** — 使用 `@service`、`@module`、`@router` 等装饰器，零继承
- **拓扑启动** — Kahn 算法确保依赖优先启动
- **依赖注入** — `deps=[DBService]` 自动注入为 `self.db_service`
- **生命周期管理** — `@after_config`/`@after_init`/`@before_startup`/`@before_shutdown` 钩子
- **ASGI 兼容** — 基于 Starlette，支持 uvicorn 等 ASGI 服务器
- **模块化架构** — 层级化组合，模块可嵌套

## 设计原则

1. **装饰器驱动** — 代码即配置，无需复杂配置
2. **异步优先** — 基于 async/await，高性能
3. **显式依赖** — 依赖声明清晰，易于理解和测试
4. **约定优于配置** — 自动注入、自动挂载
5. **可组合性** — 通过模块组合构建复杂系统

## 安装

```bash
pip install canary-framework
```

## 快速开始

```python
from canary_framework import module, service, after_config, before_shutdown

@service(name="database")
class DatabaseService:
    def __init__(self):
        self.connection = None
    
    @after_config
    async def connect(self):
        self.connection = "connected"
        print("Database connected")
    
    @before_shutdown
    async def disconnect(self):
        self.connection = None
        print("Database disconnected")

@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        return await self.database_service.query(f"SELECT * FROM users WHERE id={user_id}")

@module(name="app", services=[DatabaseService, UserService])
class AppModule:
    pass

# 使用 uvicorn 运行
# uvicorn main:AppModule --host 0.0.0.0 --port 8000
```

## Web 示例

```python
from canary_framework import module, service, router, get, post, after_config

@service(name="db")
class DatabaseService:
    @after_config
    async def connect(self):
        print("Database connected")

@router(name="api", prefix="/api", deps=[DatabaseService])
class ApiRouter:
    @get("/hello")
    async def hello(self, request):
        return {"message": "Hello from Canary!"}
    
    @post("/echo")
    async def echo(self, request):
        data = await request.json()
        return {"echo": data}

@module(name="app", services=[DatabaseService, ApiRouter])
class AppModule:
    pass
```

## 文档

📖 完整文档: [Canary Framework Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

中文文档: [docs/zh/](./docs/zh/) · English: [docs/en/](./docs/en/)

### 文档结构

- **快速入门** — 从零开始构建完整应用
- **服务** — 服务定义、依赖注入、生命周期
- **模块** — 模块组合、层级结构
- **Web 路由** — 路由、HTTP 方法、请求处理
- **依赖注入** — DI 系统、拓扑排序、注册表
- **生命周期** — 生命周期钩子、最佳实践
- **核心概念** — 设计原则、架构、底层原理
- **API 参考** — 完整 API 文档

## 架构

```
src/canary_framework/
├── common/              # 共享类型、枚举、异常
├── core/                # 核心基类
│   ├── module.py       # ModuleBase - 模块基类
│   ├── service.py      # ServiceBase - 服务基类
│   └── router.py       # RouterBase - 路由基类
├── decorators/         # 装饰器实现
│   ├── module.py       # @module
│   ├── service.py      # @service
│   ├── router.py       # @router, @get/@post/...
│   └── lifecycle.py    # 生命周期钩子
└── engine/             # 核心引擎
    ├── registry.py     # Registry - 服务注册表
    ├── injector.py     # 依赖注入、拓扑排序
    └── hooks.py        # 生命周期钩子
```

### 生命周期流程

```
AppModule.configure()
  ├── 收集所有服务
  ├── 构建依赖图
  ├── 拓扑排序 (Kahn 算法)
  ├── 实例化服务
  ├── 注入依赖
  └── 调用每个服务的 configure() + @after_config 钩子

AppModule.init()
  └── 调用每个服务的 init() + @after_init 钩子

AppModule.startup()
  └── 调用每个服务的 startup() + @before_startup 钩子

AppModule.shutdown()
  └── 逆拓扑顺序调用 shutdown() + @before_shutdown 钩子
```

## 社区

- 💬 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions)
- 🐛 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues)
- 📖 [Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

## 贡献

参见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## License

[Apache 2.0](./LICENSE) · Copyright 2026 张文博 (Canary)
