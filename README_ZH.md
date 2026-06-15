<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">轻量级 Python 异步服务框架 —— 装饰器驱动，注解式依赖注入</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/canary-framework/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img src="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework"><img src="https://img.shields.io/github/stars/HotcocoaCanary/Canary-Framework?style=social" alt="GitHub Stars"></a>
</p>

---

Canary Framework 是一个**装饰器驱动**的 Python 异步服务框架。核心理念：**服务是最小单元，模块组合服务，模块本身也是服务。**

## 核心特性

- **装饰器驱动** — 使用 `@service` 和 `@module` 装饰器，需显式基类继承
- **注解式依赖注入** — 用类型注解声明依赖：`db: Database`，无样板代码
- **拓扑启动** — Kahn 算法确保依赖优先启动
- **生命周期管理** — `@before_startup` / `@before_shutdown` 钩子
- **ASGI 兼容** — 基于 Starlette，支持 uvicorn 等 ASGI 服务器
- **模块化架构** — 层级化组合，模块可嵌套
- **OpenAPI 支持** — 自动生成 Swagger UI 和 ReDoc 文档

## 安装

```bash
pip install canary-framework
```

## 快速开始

```python
from canary_framework import service, module
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router

@service()
class Database(ServiceBase):
    async def init(self):
        await super().init()
        self.conn = "connected"

@service()
class UserService(ServiceBase):
    db: Database

    async def get_user(self, user_id: int):
        return {"id": user_id, "name": "Alice"}

@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["users"])
    user_service: UserService

    @router.get("/users/{user_id}")
    async def get_user(self, user_id: int) -> dict:
        return self.user_service.get_user(user_id)

    @router.post("/users")
    async def create_user(self, body: dict) -> dict:
        return {"id": 1, **body}

@module(services=[Database, UserService, Api])
class App(ModuleBase):
    pass

# ---- 入口 ----

async def setup():
    app = App()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn

    app = asyncio.run(setup())
    uvicorn.run(app, lifespan="on")
```

## 配置

使用 `@config` 装饰器和 `CanaryConfig` 自定义框架行为：

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    openapi_title: str = "My API"
    log_level: str = "DEBUG"

@module(services=[AppConfig, Database, Api])
class App(ModuleBase):
    config: AppConfig

async def setup():
    app = App()
    await app.init()
    return app, app.config
```

## Web 示例（带 OpenAPI）

```python
from canary_framework import service, module
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from pydantic import BaseModel, Field

class UserRequest(BaseModel):
    name: str = Field(description="用户名")
    email: str = Field(description="用户邮箱")

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

@service()
class Users(ServiceBase):
    router = Router(prefix="/users", tags=["Users"])

    @router.get("/", summary="获取用户列表", description="获取所有用户")
    async def list_users(self) -> list[UserResponse]:
        return []

    @router.post("/",
          summary="创建用户",
          description="创建新用户",
          request_model=UserRequest,
          response_model=UserResponse)
    async def create_user(self, body: UserRequest) -> UserResponse:
        return UserResponse(id=1, name=body.name, email=body.email)

@module(services=[Users])
class App(ModuleBase):
    pass
```

## OpenAPI 文档

启动应用后，访问自动生成的文档：
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## 架构

```
src/canary_framework/
├── common/              # 共享基础设施
│   ├── config.py        # CanaryConfig
│   ├── errors.py        # 框架异常
│   ├── logging.py       # 框架日志
│   └── types.py         # 数据类、标记和类型别名
├── core/                # 基类
│   ├── module/
│   │   └── _base.py     # ModuleBase — 编排和依赖注入
│   ├── service/
│   │   ├── _base.py     # ServiceBase — 生命周期和 ASGI
│   │   └── _hooks.py    # 生命周期钩子调用
│   └── router/
│       ├── _base.py     # Router — 路由收集和 ASGI 路由
│       └── _utils.py    # 路由处理器构建
├── decorators/          # 装饰器实现
│   ├── module.py        # @module
│   ├── service.py       # @service
│   ├── config.py        # @config
│   └── lifecycle.py     # @before_startup, @before_shutdown
└── engine/              # 运行时引擎
    ├── registry.py      # 服务注册表
    ├── dependencies.py  # 拓扑排序 + resolve_deps
    ├── openapi.py       # OpenAPI schema 生成
    └── params.py        # 路由参数解析
```

### 依赖注入流程

```
@service() class MyService:
    db: Database      ←  1. 用户通过类型注解声明依赖

resolve_deps(MyService)
    → get_type_hints() 读取 {db: Database}
    → 按 CF_SERVICE_MARKER 过滤
    → 返回 {"db": Database}

    ↓ 拓扑排序：Kahn 算法构建依赖顺序
    ↓ 实例化：按顺序创建实例
    ↓ 注入：

setattr(instance, "db", db_instance)   ←  2. 按注解键名注入
```

### 生命周期流程

```
app.init()
  ├── 注册所有服务及传递依赖
  ├── 拓扑排序 (Kahn 算法)
  ├── 实例化服务
  ├── 注入依赖 (注解驱动)
  ├── 按拓扑顺序调用每个服务的 init()

app.startup()
  ├── 调用 @before_startup 钩子
  └── 按拓扑顺序调用每个服务的 startup()

app.shutdown()
  ├── 调用 @before_shutdown 钩子
  └── 逆拓扑顺序调用每个服务的 shutdown()
```

## 示例

[examples/](./examples/) 目录包含可运行的、经过测试的示例：

| 文件 | 描述 |
|---|---|
| `01_standalone.py` | 单服务 + Router 独立模式 |
| `02_module_compose.py` | 模块组合多个服务 |
| `03_nested_modules.py` | 嵌套模块层级 |
| `04_module_router.py` | 模块自带 Router |
| `05_config.py` | 使用 @config() + CanaryConfig 配置 |
| `06_lifecycle.py` | 生命周期钩子 (before_startup, before_shutdown) |
| `07_validation.py` | Pydantic 请求/响应验证 |
| `08_parameters.py` | 路径、查询、请求体参数绑定 |
| `09_openapi.py` | OpenAPI 标题/版本/描述自定义 |
| `10_full_app.py` | 完整博客 API + 嵌套模块 |

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
