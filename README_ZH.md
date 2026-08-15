<h1 align="center">Canary Framework 0.7</h1>

<p align="center">一个强类型、装饰器驱动的异步生命周期与依赖注入框架。</p>

[English](README.md) · [中文文档](docs/zh/index.md) · [变更日志](CHANGELOG.md)

## 安装

```bash
pip install canary-framework
```

需要 Python 3.12+。

## 核心模型

- **Canary** 是最小运行单元 —— 一个被 `@canary` 标记的普通 Python class。依赖通过 `__init__` 的类型注解声明；`@start`、`@stop` 声明可选的生命周期行为。
- **Flock** 是 `Canary.run()` 返回的编排器。它接收一个根 Canary，发现其传递依赖，进行拓扑排序，并按依赖顺序驱动完整生命周期。

## 快速开始

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

## 依赖注入

Canary 通过构造函数类型注解声明依赖，无需额外 DSL：

```python
@canary
class UserService:
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache
```

`Canary.run()` 从根节点解析依赖图，为每个 Canary 类型注入一个共享实例，并按拓扑顺序驱动初始化与启动。

## 生命周期

`@start` 与 `@stop` 映射到 Python 原生异步上下文管理协议（`__aenter__` / `__aexit__`），因此 Canary 既能在 `Flock` 下运行，也能独立运行：

```python
database = Database(config)
async with database:
    ...  # 运行中
```

## 示例

[`examples/`](examples) 中有多个可运行示例，从最小 Canary 逐步到依赖注入、生命周期 Hook、独立使用与分层应用。

## 破坏性发布

0.7.0 完全移除了 Service / Router / Module 的 web 层。迁移说明见[新特性](docs/zh/whats-new.md)。

## 许可证

Apache-2.0。
