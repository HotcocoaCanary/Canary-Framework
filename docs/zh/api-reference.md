# API 参考

全部公开名字都从 `canary_framework` 导出。

```python
from canary_framework import (
    Canary, dep,                                  # 声明
    init, start, stop, Phase,                     # 阶段
    advance, unwind, Scope, scope_of, deps_of,    # 引擎
    CanaryError, DeclarationError, ConstructionError,
    CircularDependencyError, LifecycleError,      # 异常
)
```

## 声明

### `class Canary`

单元基类。继承它即为一个单元。

| 成员 | 说明 |
|---|---|
| `async init()` | 沿依赖推进 `init` 阶段。 |
| `async start()` | 沿依赖推进 `start` 阶段。未先 `init()` 时抛 `LifecycleError`。 |
| `async stop()` | 按台账逆序回收整个作用域。幂等。 |
| `async __aenter__()` | 依次调用 `init()` 与 `start()`，失败时回收并原样抛出。返回自身。 |
| `async __aexit__(...)` | 调用 `stop()`，不吞掉异常。 |

子类可以覆盖这些方法并用 `super()` 组合。阶段钩子的名字不得与它们冲突。

### `dep(cls)`

声明一条依赖，返回值标注为 `cls` 的实例类型。

```python
class UserService(Canary):
    database = dep(Database)
```

- 属性名由使用者决定，与被依赖的类名无关。
- 依赖在 `@init` 之后可用；在 `__init__` 中读取抛 `LifecycleError`。
- `cls` 不是 `Canary` 子类时抛 `DeclarationError`，检查发生在类体求值时。

## 阶段

### `init` / `start` / `stop`

框架提供的三个 `Phase` 实例，同时是标记方法用的装饰器。

```python
class Database(Canary):
    @start
    async def connect(self) -> None: ...
```

`start` 的前驱是 `init`。`stop` 不由 `advance()` 推进，由 `Canary.stop()` 按台账消费。

### `class Phase(name, *, after=None)`

一个阶段。可调用，调用的效果是给方法打上本阶段的标记。

| 参数 | 说明 |
|---|---|
| `name` | 阶段名。作用域用它作为推进记录与台账的键。 |
| `after` | 前驱阶段。前驱未完成时推进本阶段抛 `LifecycleError`。 |

```python
migrate = Phase("migrate", after=init)
```

## 引擎

### `async advance(unit, phase)`

在 `unit` 的依赖图上推进一次 `phase`：先推进依赖，再运行自身的钩子。同一个单元的同一个
阶段只运行一次；互不依赖的依赖同时推进。

### `async unwind(scope, phase, *, undoing)`

逆序消费 `undoing` 阶段的台账，在每个单元上执行 `phase` 的钩子。单个钩子失败不中断回收，
异常被收集并作为列表返回。台账无论成败都会排空。

```python
errors = await unwind(scope_of(unit), stop, undoing=start)
```

### `class Scope`

一次运行共享的状态。

| 属性 | 说明 |
|---|---|
| `instances` | `dict[type, object]`，类型到共享实例。 |
| `phases` | `dict[tuple[type, str], Future]`，进行中或已完成的推进。失败的推进不留记录。 |
| `entered` | `dict[str, dict[type, object]]`，阶段名到进入该阶段的单元，以类型为键，按进入顺序。 |
| `known` | `dict[str, Phase]`，本作用域推进过的阶段。 |

`phases`、`entered` 与 `known` 用于观察，其结构不在[兼容性承诺](versioning.md#public-api)范围内。

| 方法 | 说明 |
|---|---|
| `instance(cls)` | 返回该类型在本作用域内的唯一实例，首次取用时无参构造。 |
| `adopt(unit)` | 把实例登记进本作用域。 |
| `provide(cls, unit)` | 把 `unit` 登记为整张图上 `cls` 的实例。须在生命周期开始之前调用。 |
| `resolve(cls)` | `cls` 的实际类型：登记过替身时为替身的类型，否则为 `cls`。 |

### `scope_of(unit)`

返回单元所在的作用域。根单元在第一次取用时得到一个新作用域。

### `deps_of(cls)`

返回 `cls` 声明的依赖，基类在前、按定义顺序、按类型去重。

## 异常

全部继承 `CanaryError`，因此可用一次 `except CanaryError` 统一捕获。

| 异常 | 何时抛出 |
|---|---|
| `CanaryError` | 基类，本身不抛出。 |
| `DeclarationError` | `dep()` 的参数不是 `Canary` 子类。 |
| `ConstructionError` | 单元需要构造参数。携带 `unit`。 |
| `CircularDependencyError` | 依赖成环。携带 `cycle`，是实际走过的路径。 |
| `LifecycleError` | 在生命周期之外使用单元：`__init__` 中读取依赖，或前驱阶段未完成。 |

回收阶段的多个失败合并为标准库的 `ExceptionGroup`，不是 `CanaryError` 的子类。
