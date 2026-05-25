<p align="center">
  <h1 align="center">CF (Canary Framework)</h1>
  <p align="center">轻量级 Python 服务框架 —— 装饰器驱动，零样板代码</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/cf/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
</p>

---

CF 是一个**装饰器驱动**的服务框架。核心思想：**服务即最小单元，模块组合服务，模块本身也是服务**。

## 特性

- **装饰器 API** —— `@service` / `@module` / `@config` 声明即用，无需继承基类
- **拓扑启动** —— 基于 Kahn 算法自动排序，保证被依赖的先启动
- **依赖注入** —— `deps=[DBService]` 自动注入为 `self.db_service`
- **配置管理** —— `@config` + pydantic-settings，自动读取 `.env` 和环境变量
- **生命周期** —— `@on_init` / `@on_start` / `@on_end` 钩子，sync/async 自适应
- **Web 集成** —— `WebCanary` 一键接入 FastAPI + Uvicorn
- **Context 系统** —— parent 链向上委托配置和依赖解析

## 安装

```bash
pip install cf          # 核心库
pip install cf[web]     # 含 FastAPI 支持的完整安装
```

## 快速开始

```python
import asyncio
from cf import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self):
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

if __name__ == "__main__":
    async def main():
        app = Canary(App)
        await app.init()
        await app.start()

    asyncio.run(main())
```

## Web 示例

```python
import asyncio
from cf import service, module, on_init, Context, config
from cf.web.fastapi import web, get, WebCanary

@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

@web()
@module(name="AppModule", config=AppConfig, services=[])
class AppModule:
    @get("/health")
    async def health(self):
        return {"status": "ok"}

async def main():
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```

## 架构概览

```
cf/
├── core/
│   ├── decorators/          # @config, @service, @module, @on_init/start/end
│   ├── engine/              # Canary(编排), Context(上下文), Injector(DI), Sorter(拓扑)
│   ├── registry/            # 注册中心
│   └── utils/               # 命名工具
└── web/
    └── fastapi/             # WebCanary 引擎, @web, @router, @get/@post/...
```

```
Canary.init()
  ├── _collect()            递归发现 @service/@module
  ├── _validate()           校验依赖完整性
  ├── topological_sort()    Kahn 拓扑排序
  ├── _build_context_tree() 构建 Context parent 链
  └── 按拓扑序: DI → 配置加载 → on_init(ctx)
Canary.start()
  └── 按拓扑序: on_start()
Canary.stop()
  └── 按逆序: on_end()
```

## 文档

完整文档见 [Wiki](https://github.com/HotcocoaCanary/Canary-Framework/wiki) 或 [docs/](./docs/zh/) 目录。

- [快速开始](./docs/zh/quickstart.md)
- [核心概念](./docs/zh/core-concepts.md)
- [服务](./docs/zh/services.md)
- [模块](./docs/zh/modules.md)
- [配置](./docs/zh/configuration.md)
- [生命周期](./docs/zh/lifecycle.md)
- [依赖注入](./docs/zh/dependency-injection.md)
- [Web 集成](./docs/zh/web-integration.md)
- [API 参考](./docs/zh/api-reference.md)

English docs: [docs/en/](./docs/en/)

## 社区

- 💬 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions) —— 提问、交流
- 🐛 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues) —— Bug 报告、功能请求
- 📖 [Wiki](https://github.com/HotcocoaCanary/Canary-Framework/wiki) —— 完整文档

## 贡献

欢迎贡献！见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可证

[Apache 2.0](./LICENSE) · Copyright 2026 张文博 (Canary)
