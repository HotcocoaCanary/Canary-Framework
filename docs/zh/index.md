# Canary Framework

一个强类型、装饰器驱动的异步生命周期与依赖注入框架。

框架包含两个核心概念：

- **Canary** —— 最小运行单元。一个被 `@canary` 标记的普通 Python class，依赖来自 `__init__` 类型注解。
- **Flock** —— `Canary.run()` 返回的编排器，驱动一个 Canary 的完整传递依赖图。

## 亮点

- 通过原生构造函数类型注解完成依赖注入 —— 无需 DSL。
- `@start`、`@stop` 生命周期 Hook 映射到 Python 原生 `__aenter__` / `__aexit__` 协议。
- 自动构建依赖图并拓扑排序。
- 启动失败回滚与确定性的逆序关闭。
- Canary 既可独立运行（`async with ...`），也可在 `Flock` 下运行（`Canary.run()`）。

## 示例

```python
import asyncio

from canary_framework import canary, start, stop


@canary
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config

    @start
    async def connect(self) -> None: ...

    @stop
    async def disconnect(self) -> None: ...


@canary
class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database


async def main() -> None:
    async with UserService.run() as flock:
        assert flock[Database] is flock[UserService].database


asyncio.run(main())
```

## 导航

- [快速开始](quickstart.md)
- [Canary](canary.md)
- [生命周期](lifecycle.md)
- [依赖注入](dependency-injection.md)
- [Flock](flock.md)
- [架构](architecture.md)
- [API 参考](api-reference.md)
