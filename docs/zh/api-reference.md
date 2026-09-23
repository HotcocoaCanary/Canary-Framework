# API 参考

全部公开名字都从 `canary_framework` 导出。

```python
from canary_framework import (
    Canary, dep,                                  # 声明
    init, start, stop, Phase,                     # 阶段
    enter, leave, Scope, scope_of, deps_of,       # 引擎
    CanaryError, DeclarationError, ConstructionError,
    CircularDependencyError, LifecycleError,      # 异常
)
```

## 声明

### `class Canary`

单元基类。继承它即为一个单元。

| 成员 | 说明 |
|---|---|
| `async init()` | 沿依赖进入 `init` 阶段。 |
| `async start()` | 沿依赖进入 `start` 阶段。失败时先释放它启动的一切再抛出。未先 `init()` 时抛 `LifecycleError`。 |
| `async stop()` | 停止本单元（有依赖者正在启动、运行或停止时跳过），再以同样的方式尝试它的依赖。在根单元上即整张图。幂等。 |
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

`start` 的前驱是 `init`，离开它时运行 `stop`：
`start = Phase("start", after=init, leave=stop)`。

### `class Phase(name, *, after=None, leave=None)`

一个阶段。可调用，调用的效果是给方法打上本阶段的标记。

| 参数 | 说明 |
|---|---|
| `name` | 阶段名。作用域以它为键记录每个单元在该阶段上的状态。 |
| `after` | 前驱阶段。尚未进入前驱时进入本阶段抛 `LifecycleError`。 |
| `leave` | 离开本阶段时运行的阶段：`leave()` 运行它的钩子，在本阶段进入失败或被取消的单元也立即运行。`start` 的是 `stop`。 |

```python
rollback = Phase("rollback")
migrate = Phase("migrate", after=init, leave=rollback)
```

## 引擎

`Canary` 的方法就是这两个函数：`unit.init()` 即 `enter(unit, init)`，`unit.start()` 即
`enter(unit, start)`，`unit.stop()` 即 `leave(unit, start)`。自定义阶段直接调用它们。

### `async enter(unit, phase)`

在 `unit` 的依赖图上进入 `phase`：先依赖，再运行自身的钩子。同一个单元的同一个阶段只运行
一次；互不依赖的单元同时进入。依赖图先被检查——环、或尚未进入前驱阶段的单元，都在任何
钩子运行之前报告。一个失败不会取消其他单元；`phase` 声明了 `leave` 时，失败的单元立即运行
离开钩子，这次调用在释放它启动的一切之后才抛出。

### `async leave(unit, phase)`

离开 `unit` 的 `phase`：先本单元——有依赖者正在进入、已进入或正在离开时跳过，不报错——再
以同样的方式尝试它的每个依赖。运行的是 `phase.leave` 的钩子。在根单元上即整张图。本单元
仍在进入时先等进入结束。单个钩子失败不中断其余单元，异常合并为一个 `ExceptionGroup` 抛出。
`phase` 没有声明 `leave` 时抛 `LifecycleError`。

```python
await enter(unit, migrate)
await leave(unit, migrate)      # 运行 @rollback
```

### `class Scope`

一次运行共享的状态。

| 属性 | 说明 |
|---|---|
| `instances` | `dict[type, object]`，类型到共享实例。 |
| `graph` | `dict[type, tuple[type, ...]]`，依赖图：每个单元的依赖，按拓扑序。 |
| `dependents` | `dict[type, list[type]]`，依赖图的反向边。 |
| `tracks` | `dict[tuple[type, str], Track]`，每个单元在每个阶段上的状态。 |
| `known` | `dict[str, Phase]`，本作用域进入过的阶段。 |

`graph`、`dependents`、`tracks` 与 `known` 用于观察，其结构不在[兼容性承诺](versioning.md#public-api)范围内。

| 方法 | 说明 |
|---|---|
| `instance(cls)` | 返回该类型在本作用域内的唯一实例，首次取用时无参构造。 |
| `adopt(unit)` | 把实例登记进本作用域。 |
| `provide(cls, unit)` | 把 `unit` 登记为整张图上 `cls` 的实例。须在生命周期开始之前调用。 |
| `resolve(cls)` | `cls` 的实际类型：登记过替身时为替身的类型，否则为 `cls`。 |
| `key_of(unit)` | `unit` 在本作用域内登记的类型；替身为它所替换的类型。 |
| `entered(phase)` | 持有 `phase` 所获取东西的单元——已进入、尚未离开——以类型为键。 |

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
| `CircularDependencyError` | 依赖成环；在任何钩子运行之前抛出。携带 `cycle`，即走到环上的路径。 |
| `LifecycleError` | 在生命周期之外使用单元：`__init__` 中读取依赖，或前驱阶段未完成。 |

回收阶段的多个失败合并为标准库的 `ExceptionGroup`，不是 `CanaryError` 的子类。
