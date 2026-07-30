<h1 align="center">Canary Framework 0.6</h1>

<p align="center">基于 Service、Router、Module 的强类型装饰器式 Python 异步框架。</p>

[English](README.md) · [中文文档](docs/zh/index.md) · [变更日志](CHANGELOG.md)

## 安装

```bash
pip install canary-framework
```

需要 Python 3.12+。

## 核心模型

- **Service** 负责生命周期、依赖注入与领域逻辑，不是 ASGI 应用。
- **Router** 是最小可运行 HTTP 应用。少量端点逻辑可以保留在 Router；需要复用或脱离 HTTP 测试时提取为 Service。
- **Module** 通过 `children` 显式组合节点，形成依赖作用域，并递归聚合后代 Router。
- 运行根必须先执行 `await app.init()`。ASGI lifespan 只负责 startup/shutdown，绝不负责初始化。
- `on_init` 用于结构状态；依赖事件循环的长生命周期资源放在 `on_startup`，并在 `on_shutdown` 释放。
- 配置属于运行根/Module 上下文，不是注入式 Service。根配置唯一拥有 OpenAPI 元数据、安全方案与文档路径。

## 快速开始

```python
import asyncio

import uvicorn

from canary_framework import get, router
from canary_framework.core import RouterBase


@router(prefix="/hello", tags=("Hello",))
class HelloRouter(RouterBase):
    @get("")
    async def hello(self) -> dict[str, str]:
        return {"message": "Hello, Canary!"}


async def setup() -> HelloRouter:
    app = HelloRouter()
    await app.init()
    return app


application = asyncio.run(setup())
uvicorn.run(application, lifespan="on")
```

访问 `http://127.0.0.1:8000/hello`、`/docs`、`/redoc` 或 `/openapi.json`。

## 组合与传递式 DI

```python
from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

@service()
class Greeting(ServiceBase):
    def message(self, name: str) -> str:
        return f"Hello, {name}!"

@router(prefix="/api")
class ApiRouter(RouterBase):
    greeting: Greeting

    @get("/hello/{name}")
    async def hello(self, name: str) -> dict[str, str]:
        return {"message": self.greeting.message(name)}

@module(children=(ApiRouter,))
class App(ModuleBase):
    pass
```

`Greeting` 由 Router 注解传递发现，Module 只列显式组合节点。多个兄弟作用域需要共享同一 Service 实例时，将该 Service 提升到最近的共同父 Module。

## HTTP 与 OpenAPI

使用顶层 `@get`、`@post`、`@put`、`@delete`、`@patch`。路径支持 path 模板（`/{item_id}`）与 query 模板（`/search?q={query}`）。端点支持请求/响应模型、状态码、标签、摘要、描述、废弃标记、operation ID 与额外响应。

嵌套 Module/Router 的 prefix、tags、security 按确定顺序传播。运行根编译一张路由表与一份 OpenAPI。路由、文档路径、operation ID、安全方案与 schema 名冲突会在初始化时失败。

## 示例

[`examples/`](examples) 中有十个可运行示例，从独立 Router 逐步到嵌套作用域、校验、OpenAPI 与分层应用。`04_module_aggregation.py` 演示递归路由聚合。

## 破坏性发布

0.6.0 不提供 0.5.x 兼容层。迁移表见[新特性](docs/zh/whats-new.md)。

## 许可证

Apache-2.0。
