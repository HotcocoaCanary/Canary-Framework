# 单元

单元是继承了 `Canary` 的普通类。`Canary` 做两件事：把这个类纳入依赖图（于是别人可以
`dep()` 它），并给它四个生命周期动作。

```python
from canary_framework import Canary, dep, init, start, stop


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn)

    @stop
    async def close(self) -> None:
        await self.pool.close()
```

除此之外它仍是普通 Python 类，可以继承、混入、嵌套。

## 四个动作

| 动作 | 做什么 |
|---|---|
| `Unit()` | 无参构造。不运行任何钩子，依赖此时尚不可用。 |
| `await unit.init()` | 沿依赖进入 `init` 阶段。 |
| `await unit.start()` | 沿依赖进入 `start` 阶段。 |
| `await unit.stop()` | 停止本单元，再停止不再被需要的依赖。 |

`async with unit` 是便利写法：进入时依次调用 `init()` 与 `start()`，退出时调用
`stop()`。三个动作都经由本类的方法，因此子类的覆盖在这条路径上同样生效。

## 无参构造

单元一律由框架无参构造，因此 `__init__` 不能有必填参数：

```python
class Database(Canary):
    def __init__(self, dsn: str) -> None:   # 不可以
        self.dsn = dsn
```

```
ConstructionError: cannot construct Database: missing a required argument: 'dsn'.
Units are always constructed with no arguments. Declare what it needs with dep(...)
and read the values from those dependencies in @init or @start.
```

正确写法是把构造参数改写成依赖，值在钩子里从协作者读取：

```python
class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn)
```

这条约束是有意的：`@start` 有配对的 `@stop`，而构造没有配对的析构。把需要外界输入的
事情推迟到生命周期钩子，等于让每一件事都落进一个在单元停止时回收的阶段。

## 任何单元都能当入口

依赖图上的任何一个单元都可以自己启动，此时它就是它那张图的根：

```python
async with BookRepository() as books:      # 连同它的 Database 与 Config 一起就位
    ...
```

## 覆盖与组合

生命周期方法是普通方法，可以覆盖并用 `super()` 组合：

```python
class Traced(Canary):
    async def start(self) -> None:
        log.info("starting %s", type(self).__name__)
        await super().start()
        log.info("started %s", type(self).__name__)


class Service(Traced):
    @start
    async def go(self) -> None: ...
```

阶段钩子的名字由你决定，只要不与 `init` / `start` / `stop` / `__aenter__` /
`__aexit__` 这五个名字冲突。

## 替身 {#substitutes}

单元的标记随继承传递，因此测试替身继承被替换的类型即可：

```python
class FakeDatabase(Database):
    @start
    async def connect(self) -> None:
        self.pool = InMemoryPool()
```

在生命周期开始之前把替身登记进作用域，它就替换了图中的那个实例：

```python
from canary_framework import scope_of

service = UserService()
scope_of(service).provide(Database, FakeDatabase())

async with service:
    ...
```

之后图中所有 `dep(Database)` 都取回这个实例，它按自身的类型参与生命周期：运行自己的钩子，
自己声明的依赖先进入。

作用域里已经有 `Database` 时，或实例不是 `Database` 时，登记会被拒绝。给依赖属性赋值
（`service.database = ...`）会抛 `AttributeError`：赋值只会改到这一个属性，图中其余单元
仍然取回原来的实例。

## `stop()` 是单元的动作 {#stop-is-a-unit-action}

三个动作都属于被调用的那个单元，`stop()` 与 `start()` 互为镜像：

| | 顺序 | 在图上 |
|---|---|---|
| `start()` | 先依赖，后本单元 | 拉起本单元需要的依赖 |
| `stop()` | 先本单元，后依赖 | 回收不再被其他单元使用的依赖 |

`stop()` 停止本单元——除非它仍被使用，即有依赖者正在启动、运行或停止——再以同样的方式
尝试它的每个依赖。停止根单元即回收整张图，因为它的依赖不再被任何单元使用：

```python
await service.stop()        # service，然后 database 与 cache，最后 config
```

与仍在运行的单元共享的依赖继续运行：

```python
await root.left.start()
await root.right.start()    # 二者都依赖 Shared
await root.left.stop()      # left 停止；shared 继续运行，right 还需要它
await root.right.stop()     # right，然后 shared
```

停止一个仍被使用的单元时，它被跳过，不报错。它的依赖仍会被尝试，但它们正被它使用，因此
什么都不会停止：

```python
async with service:
    await service.database.stop()    # service 仍在使用 database：什么都不会发生
```

同时停止一个单元与它的使用者，每个单元只停止一次。作用域持有整张依赖图，因此总是知道谁还
在使用一个单元。
