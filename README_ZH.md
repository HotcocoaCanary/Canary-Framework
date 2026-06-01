<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">轻量级 Python 异步服务框架 —— 装饰器驱动，零样板代码</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/canary-framework/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/HotcocoaCanary/Canary-Framework/ci.yml" alt="CI"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework"><img src="https://img.shields.io/github/stars/HotcocoaCanary/Canary-Framework?style=social" alt="GitHub Stars"></a>
</p>

---

Canary Framework 是一个**装饰器驱动**的 Python 异步服务框架。核心哲学：**服务是最小单元，模块组合服务，模块本身也是服务。**

## 核心特性

- **装饰器驱动** — 使用 `@service`、`@module`、`@router` 等装饰器，零继承
- **拓扑启动** — Kahn 算法确保依赖优先启动
- **依赖注入** — `deps=[DBService]` 自动注入为 `self.db_service`
- **生命周期管理** — `@after_config`/`@after_init`/`@before_startup`/`@before_shutdown` 钩子
- **ASGI 兼容** — 基于 Starlette，支持 uvicorn 等 ASGI 服务器
- **模块化架构** — 层级化组合，模块可嵌套
- **OpenAPI 支持** — 自动生成 Swagger UI 和 ReDoc 文档

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
from canary_framework import module, service, router, get, post, after_config

@service(name="database")
class DatabaseService:
    def __init__(self):
        self.connection = None
    
    @after_config
    async def connect(self):
        self.connection = "connected"
        print("Database connected")

@service(name="user_service", deps=[DatabaseService])
class UserService:
    async def get_user(self, user_id):
        return {"id": user_id, "name": "User"}

@router(name="api", prefix="/api", deps=[UserService])
class ApiRouter:
    @get("/users/{user_id}")
    async def get_user(self, request):
        user_id = request.path_params["user_id"]
        return await self.user_service.get_user(int(user_id))
    
    @post("/users")
    async def create_user(self, request):
        data = await request.json()
        return {"id": 1, **data}, 201

@module(name="app", services=[DatabaseService, UserService, ApiRouter])
class AppModule:
    pass

# 使用 uvicorn 运行
# uvicorn main:AppModule --host 0.0.0.0 --port 8000 --reload
```

## Web 示例（带 OpenAPI）

```python
from canary_framework import module, router, get, post
from pydantic import BaseModel, Field

class UserRequest(BaseModel):
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

class UserResponse(BaseModel):
    id: int = Field(description="用户ID")
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

@router(name="users", prefix="/users", tags=["Users"])
class UsersRouter:
    @get("/", summary="获取用户列表", description="获取所有用户")
    async def list_users(self, request):
        return {"users": []}
    
    @post("/", 
          summary="创建用户", 
          description="创建新用户",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, request, user: UserRequest):
        return {"id": 1, **user.model_dump()}, 201

@module(name="app", services=[UsersRouter])
class AppModule:
    pass
```

## OpenAPI 文档

启动应用后，访问自动生成的文档：
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## 文档

📖 完整文档: [Canary Framework Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

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
│   ├── errors.py        # 框架异常
│   ├── markers.py       # 元数据标记和访问器
│   └── types.py         # 数据类和类型别名
├── core/                # 核心基类
│   ├── module.py        # ModuleBase - 模块编排
│   ├── service.py       # ServiceBase - 生命周期管理
│   └── router.py        # RouterBase - ASGI 路由
├── decorators/         # 装饰器实现
│   ├── module.py        # @module 装饰器
│   ├── service.py       # @service 装饰器
│   ├── router.py        # @router, @get/@post/... 装饰器
│   └── lifecycle.py     # @after_config, @after_init 等
└── engine/             # 核心引擎组件
    ├── registry.py      # Registry - 服务注册表
    ├── injector.py      # 依赖注入、拓扑排序
    ├── hooks.py         # 生命周期钩子发现
    ├── openapi.py       # OpenAPI schema 生成
    ├── utils.py         # 辅助工具函数
    └── logging.py       # 日志工具
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

## 测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/
```

## 社区

- 💬 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions)
- 🐛 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues)
- 📖 [Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

## 贡献

参见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可证

[Apache 2.0](./LICENSE) · Copyright 2026 张文博 (Canary)