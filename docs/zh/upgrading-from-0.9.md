# 从 0.9.x 升级

0.10.0 重写了核心，1.0 沿用这一核心。从 0.9.x 升级时，公开 API 完全不兼容，且没有兼容层；
本页列出变化与迁移方式。之后再看 [1.0 新特性](whats-new.md) 了解 0.10 之后新增的内容。

## 单元是一个基类

`@cocoa` 装饰器与 `Canary` 运行时容器都不再存在。继承 `Canary` 即为一个单元，它自己就
能走完自己的一生：

```python
class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None: ...

    @stop
    async def close(self) -> None: ...


async with UserService() as service:      # 整张图按依赖顺序就位
    ...
```

改用基类而非装饰器，是为了让 `service.init()`、`async with service` 与 `self.config`
在类型检查器和 IDE 里都是可见的——装饰器无法改变一个类的静态类型。

## `dep()` 取代 `deps=[...]`

依赖由描述符声明，不再由装饰器参数列出：

```python
class AlertDispatcher(Canary):
    sink = dep(LoggingAlertSink)
```

- **属性名由你决定**，不再是被依赖类名的 snake_case，因此实现类可以有一个抽象的注入名。
- **类型是推断出来的**，`self.sink` 就是 `LoggingAlertSink`，不必另写注解。
- **声明不需要求值**，因此不受 `from __future__ import annotations`、`if TYPE_CHECKING`
  或函数作用域影响。0.9.x 的类级注解注入在这三种情形下会静默失效。

## 阶段是一等对象

`@init` / `@start` / `@stop` 是 `Phase` 的实例，既是装饰器也是引擎的参数。加一个阶段
不需要注册：

```python
migrate = Phase("migrate", after=init)
```

`after` 声明前驱，因此未 `init()` 就 `start()` 会抛 `LifecycleError`，而不是静默跳过。

## 覆盖就是覆盖

钩子按属性名解析，语义与普通方法一致：子类覆盖同名钩子即替换，需要叠加时使用 `super()`。
0.9.x 按函数身份去重，导致覆盖变成叠加。

生命周期方法本身也可以覆盖：

```python
class Traced(Canary):
    async def start(self) -> None:
        log.info("starting")
        await super().start()
```

## 引擎是两个函数

自定义阶段由两个函数驱动，`Canary` 的方法就是它们的包装：

- `enter(unit, phase)` 在依赖图上进入一个阶段，依赖在前；
- `leave(unit, phase)` 离开它，本单元在前。

运行时容器及其独立的生命周期状态机都已删除；每个单元在作用域的依赖图中持有自己的状态。
依赖链的深度不再受 Python 递归上限约束（此前约 493 层）。见[架构](architecture.md)。

## 移除

- `@cocoa`、`Canary(*roots)` 运行时容器、`canary.order`、`canary.instances`、
  `canary[Type]`、`canary.lifespan`、`start_concurrency=`、装配摘要、事件循环延迟探针。
- `LifecycleState` 与八态状态机。
- 按类名 snake_case 注入、类级注解注入、`Config` 与日志注入。
- `canary_framework.web` 在 0.9.3 开发期已删除，本版本未恢复。

## 迁移

| 0.9.x | 1.0 |
|---|---|
| `@cocoa(deps=[Database])` + `self.database` | `class X(Canary)` + `database = dep(Database)` |
| `@on_init` / `@on_start` / `@on_stop` | `@init` / `@start` / `@stop` |
| `canary = Canary(Root)` | `root = Root()` |
| `await canary.init()` / `.start()` / `.stop()` | `await root.init()` / `.start()` / `.stop()` |
| `async with Canary(Root) as c` | `async with Root() as root` |
| `canary[Database]` | 从声明它的单元上读，或 `scope_of(root).instances[Database]` |
| `Canary(Root, start_concurrency=8)` | 并发已是默认行为，无需配置 |
| `app = FastAPI(lifespan=canary.lifespan)` | 自写三行 `asynccontextmanager` |
