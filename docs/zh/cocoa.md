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

## 声明依赖

cocoa 通过 `deps=[...]` 声明依赖：

```python
@cocoa(deps=[Config])
class Database:
    # self.config 会在 start() 阶段注入
    pass
```

依赖是**惰性注入**的 —— 不走 `__init__`。在 `start()` 阶段，运行时为每个依赖设置
`self.<snake_case 名>`（`Config` → `self.config`，`UserService` → `self.user_service`）。
这让构造函数保持空、单元构建廉价。

```python
@cocoa(deps=[Database, Cache])
class UserService:
    def __init__(self) -> None:
        # 这里无需任何依赖装配。
        self._ready = False
```

完整契约见 [依赖注入](dependency-injection.md)。

## 生命周期钩子

一个 cocoa 可以在每个阶段声明任意多个钩子。所有钩子都可选；只有依赖、没有钩子的单元也
是完整的。

| 阶段 | 装饰器 | 执行时机 |
|---|---|---|
| 初始化 | `@on_init` | `init()` 时，拓扑序 |
| 启动 | `@on_start` | `start()` 时，拓扑序，依赖已注入 |
| 停止 | `@on_stop` | `stop()` 时，逆拓扑序 |

```python
from canary_framework import cocoa, on_init, on_start, on_stop


@cocoa(deps=[Config])
class Database:
    @on_init
    def build_pool(self) -> None:
        self.pool = ConnectionPool(self.config.database_url)

    @on_start
    async def connect(self) -> None:
        await self.pool.connect()

    @on_stop
    async def disconnect(self) -> None:
        await self.pool.close()
```

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
