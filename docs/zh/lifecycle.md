# 生命周期

## 阶段

一个阶段是一次遍历的名字。框架提供三个：

```python
from canary_framework import init, start, stop
```

它们既是标记方法用的装饰器，也是 `advance()` 与 `unwind()` 的参数。

```python
class Database(Canary):
    @init
    def prepare(self) -> None: ...

    @start
    async def connect(self) -> None: ...

    @stop
    async def close(self) -> None: ...
```

同一个类的同一个阶段可以有多个钩子，按定义顺序执行；同一个方法可以同时属于多个阶段。
钩子可以是同步的，也可以是 `async def`——框架按返回值判断是否需要等待，因此返回协程的
同步函数同样成立。

## 推进：沿依赖递归

`await unit.init()` 在依赖图上推进一次 `init`：先推进依赖，再运行自身的钩子。

```python
class Config(Canary): ...


class Database(Canary):
    config = dep(Config)


class Service(Canary):
    database = dep(Database)


await Service().init()      # Config -> Database -> Service
```

两条性质：

- **同一个单元的同一个阶段只运行一次**，无论有多少单元依赖它。
- **互不依赖的依赖同时推进**，因此耗时贴着依赖链的关键路径，而不是所有单元之和。

## 栅栏

`init()` 的返回是一道栅栏：全部 `@init` 完成之后，才有任何 `@start` 运行。

```
Config.init -> Database.init -> Service.init
          ↓ 栅栏
Config.start -> Database.start -> Service.start
```

这是 `@init` 与 `@start` 的实质区别。`@init` 不获取外部资源，所以它在整张图上跑一遍时，
失败不需要回收；`@start` 获取资源，所以它有配对的 `@stop`。

未调用 `init()` 就 `start()` 会抛出：

```
LifecycleError: Service: @init has not run, call it before @start
```

## 记账与回收

单元一进入 `@start` 就被记入台账——记的是"进入"而非"完成"，因此启动到一半失败的单元
同样会被回收。

`stop()` 逆序消费台账，是唯一的回收路径：

| 调用时机 | 行为 |
|---|---|
| 从未启动 | 台账为空，空操作 |
| 只 `init()` 过 | `start` 台账为空，空操作 |
| 正常启动之后 | 逆序回收 |
| `start()` 中途失败 | 回收进入过 `@start` 的单元，含失败的那一个 |
| `start()` 仍在进行 | 等它结束（无论成败），再逆序回收 |
| 重复调用 | 台账已排空，空操作 |
| 仍有运行中的单元依赖它 | 抛 `LifecycleError` 拒绝，不回收任何东西 |

同一套规则覆盖所有情形，因此不需要状态机。

由于 `stop()` 会等待进行中的 `start()`，不要在同一张图的 `@start` 钩子里调用它：那会等待
自身。需要限时关闭时，用 `asyncio.timeout` 包住这次调用。

## 再次启动 {#starting-again}

回收时，被回收单元在 `start` 上的推进记录一并撤销，因此停止之后可以再次启动。`@init`
没有配对的回收阶段，它的记录保留，重启时不会再次运行：

```python
async with service:     # init、start、stop
    ...
async with service:     # start、stop
    ...
```

以 `after=start` 声明的阶段随 `start` 一起撤销，重启之后需要重新推进。

失败或被取消的推进不留记录，因此再次调用会重新运行。已经完成该阶段的单元不会重复运行，
重新进入 `@start` 的单元在台账中只保留一条：

```python
try:
    await service.start()
except ConnectionError:
    await service.stop()     # 回收已启动的部分
await service.start()        # 重试
```

## 失败

**启动失败。** 任一 `@start` 抛出时，台账里的单元逆序回收，随后原样抛出最初的异常：

```python
class Leaf(Canary):
    @start
    def go(self) -> None: ...

    @stop
    def bye(self) -> None:
        print("leaf 回收")


class Root(Canary):
    leaf = dep(Leaf)

    @start
    def go(self) -> None:
        raise RuntimeError("启动失败")


async with Root():        # 打印 "leaf 回收"，然后抛出 RuntimeError
    ...
```

回收过程中再出错时，该异常作为 note 附在最初那个异常上，不会盖住它。

**多个单元同时失败。** 并发推进时若有多个单元同时抛出，异常合并为一个
`ExceptionGroup`；只有一个失败时原样抛出，与顺序推进行为一致。

**回收失败。** 单个 `@stop` 抛出不中断整轮回收，其余单元照常回收，最后合并为一个
`ExceptionGroup` 抛出，即使只有一个：

```
ExceptionGroup: 1 error(s) while stopping
  RuntimeError: 关闭失败
    raised by Database.close
```

## 自定义阶段

`Phase` 是公开的，加一个阶段不需要注册：

```python
from canary_framework import Phase, advance, init

migrate = Phase("migrate", after=init)


class Schema(Canary):
    @migrate
    async def apply(self) -> None: ...


await unit.init()
await advance(unit, migrate)
```

`after` 声明前驱：前驱阶段尚未完成时推进本阶段会抛 `LifecycleError`，而不是静默跳过。

需要给新阶段配一个回收阶段时用 `unwind()`，配对关系写在调用点：

```python
from canary_framework import scope_of, unwind

errors = await unwind(scope_of(unit), rollback, undoing=migrate)
```

## 接入宿主

框架不认识任何外壳。宿主收异步上下文管理器时：

```python
@asynccontextmanager
async def lifespan(_app):
    async with service:
        yield
```

宿主收成对的启停回调时，直接给它 `service.init` / `service.start` / `service.stop`
三个方法。
