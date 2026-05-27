<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">轻量级 Python 服务框架 —— 装饰器驱动，零样板代码</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/canary-framework/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
</p>

---

Canary Framework 是一个**装饰器驱动**的服务框架。核心思想：**服务即最小单元，模块组合服务，模块本身也是服务**。

## 特性

- **装饰器 API** — `@service` / `@module` 声明即用，无需继承基类
- **拓扑启动** — 基于 Kahn 算法自动排序，保证被依赖的先启动
- **依赖注入** — `deps=[DBService]` 自动注入为 `self.db_service`
- **配置管理** — pydantic-settings + `app.config(config=...)`，自动读取 `.env` 和环境变量
- **生命周期** — `@on_config` / `@on_init` / `@on_start` / `@on_end` 钩子，sync/async 自适应
- **Web 集成** — `WebCanary` 一键接入 FastAPI + Uvicorn
- **日志脱敏** — 敏感字段 (password, secret, token) 自动屏蔽

## 安装

```bash
pip install canary-framework          # 核心库
pip install canary-framework[web]     # 含 FastAPI 支持的完整安装
```

## 快速开始

```python
import asyncio
from canary_framework import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self) -> None:
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

async def main() -> None:
    app = Canary(App)
    await app.config()
    await app.init()
    await app.start()

asyncio.run(main())
```

## Web 示例

```python
import asyncio
from pydantic import BaseModel
from canary_framework import service, module, on_config, Canary
from canary_framework.web.fastapi import router, get, WebCanary

class DBConfig(BaseModel):
    connection_string: str = "postgresql://localhost/mydb"
    pool_size: int = 10

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"
    dbservice: DBConfig = DBConfig()

@service(name="dbservice")
class DBService:
    @on_config
    def setup(self) -> None:
        print(f"DB ready at {self.connection_string}")

@router(prefix="/api", tags=["api"])
class APIRouter:
    @get("/hello")
    async def hello(self) -> dict:
        return {"message": "Hello, world!"}

@module(name="AppModule", services=[APIRouter, DBService])
class AppModule:
    pass

async def main() -> None:
    app = WebCanary(AppModule)
    await app.config(config=AppConfig())
    await app.init()
    await app.start()

asyncio.run(main())
```

## 文档

完整文档见 [Wiki](https://github.com/HotcocoaCanary/Canary-Framework/wiki) 或 [docs/](./docs/zh/) 目录。

English docs: [docs/en/](./docs/en/)

## 架构概览

```
src/canary_framework/
├── common/                  # 共享类型、枚举、异常、日志
├── core/
│   ├── decorators/          # @service, @module, 生命周期钩子
│   ├── conductor/           # Canary 引擎 (生命周期编排)
│   ├── container/           # 注册中心 (Registry)
│   └── algorithms/          # 拓扑排序, DI 注入器, 命名工具
└── web/
    └── fastapi/             # WebCanary 引擎, @router, @get/@post/...
```

```
Canary.config()
  ├── _collect()            递归发现 @service/@module
  ├── _validate()           校验依赖完整性
  ├── topological_sort()    Kahn 拓扑排序
  ├── instantiate()         创建所有服务实例
  ├── _wire_entry()         DI + 配置注入 + 子服务注入
  └── on_config 钩子        (按拓扑序)
Canary.init()
  └── 按拓扑序: on_init()
Canary.start()
  └── 按拓扑序: on_start()
Canary.stop()
  └── 按逆序: on_end()
```

## 社区

- 💬 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions)
- 🐛 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues)
- 📖 [Wiki](https://github.com/HotcocoaCanary/Canary-Framework/wiki)

## 贡献

欢迎贡献！见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可证

[Apache 2.0](./LICENSE) · Copyright 2026 张文博 (Canary)
