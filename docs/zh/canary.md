# Canary

**Canary** 是框架的最小运行单元：一个被 `@canary` 标记的普通 Python class。

```python
from canary_framework import canary


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
```

`@canary` 会：

1. 注册该类，
2. 记录其元数据，
3. 发现其生命周期 Hook，
4. 使其成为 `Canary` 的子类，从而获得异步上下文管理协议与 `state` 属性。

它**不会**向类动态添加生命周期方法。你的方法仍是普通方法，静态类型检查器可以正常识别。

## 声明依赖

Canary 通过 `__init__` 类型注解声明依赖。任何带类注解（或字符串前向引用）且无默认值的参数都被视为依赖：

```python
@canary
class UserService:
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache
```

带默认值的参数**不会**被注入：

```python
@canary
class Repository:
    def __init__(self, database: Database, timeout: float = 30.0) -> None:
        self.database = database
        self.timeout = timeout
```

这里只有 `database` 是依赖，`timeout` 保留默认值。

完整契约见[依赖注入](dependency-injection.md)。

## 生命周期 Hook

每个 Canary 每个阶段最多声明一个 Hook：

| 阶段 | 装饰器 | 执行时机 |
|---|---|---|
| 启动 | `@start` | `__aenter__` 时 |
| 停止 | `@stop` | `__aexit__` 时 |

每个 Hook 都是可选的。没有任何 Hook 的 Canary 完全合法：

```python
@canary
class UserRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
```

## 用 `run()` 编排依赖图

`Canary.run()` 是一个 classmethod，返回一个 [`Flock`](flock.md) —— 图句柄，用于发现该 Canary 的传递依赖、进行拓扑排序，并驱动整张图：

```python
@canary
class Config:
    ...


@canary
class Database:
    def __init__(self, config: Config) -> None:
        self.config = config


@canary
class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database


async with UserService.run() as flock:
    assert flock[Database] is flock[UserService].database
```

编排、回滚与关闭的细节见 [Flock](flock.md)。

## 直接使用 Canary

Canary 遵循 Python 异步上下文管理协议，因此可以不依赖 `Flock` 独立运行：

```python
database = Database(Config())

async with database:
    ...  # 运行中
```

`__aenter__` 执行 `@start`；`__aexit__` 执行 `@stop`。

你也可以显式调用协议方法：

```python
await database.__aenter__()
...
await database.__aexit__(None, None, None)
```

## `state` 属性

每个 Canary 都暴露一个来自 `LifecycleState` 的 `state` 属性：

`NEW → INITIALIZED → STARTING → RUNNING → STOPPING → STOPPED`

出错时进入 `FAILED`。详见[生命周期](lifecycle.md)。
