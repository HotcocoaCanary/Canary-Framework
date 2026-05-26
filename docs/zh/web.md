# Web 包

`canary_framework.web` 包为 Core 扩展了 HTTP 服务器能力。它是一个**插件** —— Core 不依赖 web，web 是可选的（`pip install canary-framework[web]`）。

## 架构

```
canary_framework
├── core/                    # Service、Module、DI、Lifecycle、Trace
│   └── (框架无关)
└── web/
    └── fastapi/
        ├── conductor/
        │   └── web_canary.py   # WebCanary(Canary) — 重写 start()
        └── decorators/
            └── router.py       # @router、@get、@post……
```

**核心理念：一切皆服务。** `@router` 继承自 `@service` —— 路由即服务，只不过暴露了 HTTP 端点。它像任何其他服务一样接收 DI、配置和生命周期钩子。

## WebCanary

`WebCanary` 扩展了 `Canary`，仅重写了一个方法：`start()` 启动 FastAPI + Uvicorn 服务器，而非仅调用 `on_start` 钩子。

```python
from canary_framework.web.fastapi import WebCanary

app = WebCanary(MyRootModule)
await app.config(config=AppConfig())   # wiring + on_config 钩子
await app.init()    # 与 Canary 相同：收集 → 校验 → 排序 → DI → on_init
await app.start()   # 被重写：启动 FastAPI + Uvicorn，注册路由
```

## 路由即服务

`@router` 装饰的类就是一个带有额外元数据（`prefix` 和 `tags`）的 `@service`：

```python
@router(prefix="/api/users", deps=[UserService], tags=["users"])
class UserRouter:
    user_service: UserService  # DI 注入

    @get("/{id}")
    async def get(self, id: int) -> User:
        return await self.user_service.get_by_id(id)
```

因为 `@router` 是服务，所以它支持：
- **`deps`** — DI 注入依赖
- **`@on_config` / `@on_init` / `@on_start` / `@on_end`** — 完整的生命周期

路由由 `WebCanary` 自动发现 —— 无需 `@web` 装饰器。只需将路由类放到模块的 `services` 列表（或服务的 `deps`）中，`WebCanary.start()` 就会注册所有 HTTP 路由。

## 延伸阅读

- [FastAPI 集成](./fastapi.md) — 详细用法、HTTP 方法、配置前缀
