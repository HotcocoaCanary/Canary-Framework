# 0.7.0 新特性

0.7.0 是一次破坏性重构。Service / Router / Module 的 web 层被移除，替换为纯 **Canary / Flock** 生命周期与依赖注入引擎。

## 迁移对照表

| 0.6.0 | 0.7.0 |
|---|---|
| `@service()` / `ServiceBase` | `@canary` |
| `@router()` / `RouterBase` | 已移除 |
| `@module()` / `ModuleBase` | 已移除 |
| `@get` / `@post` / … | 已移除 |
| `on_init` / `on_startup` / `on_shutdown` | `@start` / `@stop` |
| `await app.init()` + ASGI lifespan | `Canary.run()` + `await flock.start()` |
| config service | `@canary class Config` |
| OpenAPI / 文档端点 | 已移除 |

## 之前

```python
from canary_framework import get, router
from canary_framework.core import RouterBase


@router(prefix="/hello", tags=("Hello",))
class HelloRouter(RouterBase):
    @get("")
    async def hello(self) -> dict[str, str]:
        return {"message": "Hello, Canary!"}
```

## 之后

```python
from canary_framework import canary


@canary
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config


async def main() -> None:
    async with Database.run() as flock:
        assert flock[Database].config is flock[Config]


asyncio.run(main())
```

## 关键变化

- **Canary 取代 Service。** Canary 是普通 class，依赖来自 `__init__` 注解。
- **生命周期 Hook 取代生命周期方法。** `@start`、`@stop` 映射到 `__aenter__` / `__aexit__`。
- **`Flock` 取代运行根。** `Canary.run()` 返回一个 `Flock`，它发现、排序并驱动依赖图。
- **无 web 层。** 路由、OpenAPI 与配置系统被移除，框架是纯引擎。
- **独立使用。** Canary 本身就是异步上下文管理器。
