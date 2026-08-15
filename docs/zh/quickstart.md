# 快速开始

安装框架：

```bash
pip install canary-framework
```

需要 Python 3.12+。

## 声明 Canary

用 `@canary` 标记任意普通 class：

```python
from canary_framework import canary


@canary
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"
```

依赖通过 `__init__` 签名声明：

```python
from canary_framework import canary


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
```

## 添加生命周期行为

使用 `@start`、`@stop` —— 两者可选，且同步 / 异步均可：

```python
from canary_framework import canary, start, stop


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.pool = ConnectionPool(self.config.database_url)

    @start
    async def connect(self) -> None:
        await self.pool.connect()

    @stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

## 使用 Flock 运行

`Canary.run()` 返回一个 `Flock`，从根 Canary 发现依赖图，进行拓扑排序，并驱动生命周期：

```python
import asyncio

from canary_framework import canary


@canary
class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database


async def main() -> None:
    flock = UserService.run()
    await flock.start()

    try:
        users = flock[UserService]
        assert users.database is flock[Database]
    finally:
        await flock.stop()


asyncio.run(main())
```

或将其作为异步上下文管理器使用：

```python
async def main() -> None:
    async with UserService.run() as flock:
        assert flock[Database] is flock[UserService].database


asyncio.run(main())
```

## 独立运行单个 Canary

Canary 遵循 Python 异步上下文管理协议，因此可直接驱动：

```python
async def main() -> None:
    database = Database(Config())
    async with database:
        ...  # 运行中


asyncio.run(main())
```

## 下一步

- [Canary](canary.md) —— 声明与依赖契约。
- [生命周期](lifecycle.md) —— 状态机与 Hook 顺序。
- [依赖注入](dependency-injection.md) —— 前向引用、循环依赖、作用域。
- [Flock](flock.md) —— 编排、回滚与关闭。
