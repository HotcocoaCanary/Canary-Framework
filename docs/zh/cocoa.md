# Cocoa 单元

**cocoa** 是框架的最小单元：一个被 `@cocoa` 标记的普通 Python class。

```python
from canary_framework import cocoa


@cocoa
class Config:
    def __init__(self) -> None:
        self.database_url = "postgresql://localhost/dev"
```

`@cocoa` 只做一件事：给类打上一个标记。它**不**改变类、方法或构造函数 —— 你的类仍是
静态类型检查器能理解的普通类，可以廉价地继承 / 混入 / 嵌套。

## 构造：无参，这是硬规则

图上的实例**全部由框架构造**，而且是无参构造。所以：

```python
@cocoa
class Database:
    def __init__(self, dsn: str) -> None:  # ✗ 必填参数，框架造不出来
        ...
```

```text
ConstructionError: cannot construct Database: missing a required argument: 'dsn'.
Units are always constructed with no arguments — declare what it needs in
@cocoa(deps=[...]) and read the values from those dependencies in @on_init or @on_start.
```

正确的写法是把构造参数变成依赖：

```python
@cocoa
class Config:
    def __init__(self) -> None:
        self.dsn = "postgresql://localhost/dev"


@cocoa(deps=[Config])
class Database:
    @on_init
    def take_the_dsn(self) -> None:
        self.dsn = self.config.dsn  # 值从协作者那里读
```

**规则不是"不许有构造函数"，是"不许有必填参数"。** 不需要外界输入的初始化照常写在
`__init__` 里：

```python
@cocoa
class Cache:
    def __init__(self) -> None:
        self._entries: dict[str, object] = {}  # ✓ 完全合法
        self._hits = 0
```

带默认值的参数也没问题（框架不会传，用的就是默认值）。

## 声明依赖

cocoa 通过 `deps=[...]` 声明依赖：

```python
@cocoa(deps=[Config])
class Database:
    # self.config 在构造期注入
    pass
```

注入发生在构造期：运行时为每个依赖设置 `self.<snake_case 名>`（`Config` → `self.config`，
`UserService` → `self.user_service`）。因为注入属于**装配**而不是启动，`@on_init` 已经能
看到自己的协作者。

完整契约见 [依赖注入](dependency-injection.md)。

## 生命周期钩子

一个 cocoa 可以在每个阶段声明任意多个钩子。所有钩子都可选；只有依赖、没有钩子的单元也
是完整的。

| 阶段 | 装饰器 | 执行时机 | 手上有什么 |
|---|---|---|---|
| 初始化 | `@on_init` | `init()` 时，拓扑序 | 依赖已就位，但还没有任何东西开始运行 |
| 启动 | `@on_start` | `start()` 时，拓扑序 | 依赖已就位，可以获取资源、起后台任务 |
| 停止 | `@on_stop` | `stop()` 时，逆拓扑序 | 回收 `@on_start` 拿到的东西 |

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        # 只用依赖、不碰外部资源的准备工作
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        # 需要连接、需要 IO 的，归这里
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

**怎么在 `@on_init` 和 `@on_start` 之间选**：不碰外部资源的准备工作（校验、建索引、算派生
值、从配置读值）放 `@on_init`；需要连接、开文件、起后台任务的放 `@on_start` —— 因为只有
`@on_start` 拿到的东西才会被 `@on_stop` 回收。

每个钩子可以是普通函数或协程函数 —— 运行时按返回值判断，仅在需要时 `await`。

钩子是**叠加而非覆盖**的：如果混入类声明了一个 `@on_start`，本类又声明了一个，两者都会
执行 —— 混入的先、本类的后，按定义顺序。

## 用 `Canary` 编排

cocoa 在交给 [`Canary`](canary.md) 之前是惰性的；`Canary` 解析其依赖图并驱动生命周期：

```python
from canary_framework import Canary


app = Canary(UserService)
await app.init()
await app.start()
assert app[Database].config is app[Config]
await app.stop()
```

编排细节见 [运行时（Canary）](canary.md)。

## 一个已知的边界

单元是**按类型索引**的：一个类型在一张图里只有一个实例。所以"两个连不同库的 `Database`"
写不出来 —— 需要两个实例就写两个类。这是"类型即身份"这个选择的硬边界，生命周期钩子帮不
上忙。

另外，注入的属性是运行时才出现的，静态类型检查器看不见 `self.config`。目前没有既保持
"普通类"又让 mypy 满意的办法，这是这个设计尚未回答的问题。
