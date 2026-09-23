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

## 推进：依赖在前 {#advancing}

`await unit.init()` 在依赖图上推进一次 `init`：先推进依赖，再运行自身的钩子。

```python
class Config(Canary): ...


class Database(Canary):
    config = dep(Config)


class Service(Canary):
    database = dep(Database)


await Service().init()      # Config -> Database -> Service
```

三条性质：

- **同一个单元的同一个阶段只运行一次**，无论有多少单元依赖它。
- **互不依赖的单元同时推进**，因此耗时贴着依赖链的关键路径，而不是所有单元之和。
- **图检查通过之前不运行任何钩子。** 依赖图先于一切构建，因此环、或 `start()` 时某个单元的
  `@init` 尚未运行，都在任何钩子运行之前报告。

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

`stop()` 是唯一的回收路径。它停止本单元（除非仍被使用），再以同样的方式尝试它的每个依赖：

| 调用时机 | 行为 |
|---|---|
| 从未启动 | 本单元无可停止；仍会尝试它的依赖 |
| 只 `init()` 过 | 没有单元进入过 `@start`，空操作 |
| 正常启动之后 | 停止本单元，再停止不再被其他单元使用的依赖 |
| 仍被使用——有依赖者正在启动、运行或停止 | 跳过本单元，不报错；仍会尝试它的依赖 |
| `start()` 仍在进行 | 等它结束，再作判断 |
| 重复调用 | 已无可回收，空操作 |

被多个单元共享的依赖，在最后一个使用者停止之后才停止。示例见
[单元 › `stop()` 是单元的动作](canary.md#stop-is-a-unit-action)。

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

失败的 `start()` 已经释放了它获取的东西（见下文），因此重试就是再调用一次。已经完成该阶段
的单元不会重复运行：

```python
try:
    await service.start()
except ConnectionError:
    await service.start()    # 失败的那次已经自行清理
```

## 失败

**启动失败。** `start()` 自行清理：

- `@start` 抛出的单元立即执行自己的 `@stop`；
- 依赖它的单元不启动，并释放它们正在等待的依赖；
- 与它同时启动的单元不会被取消——它们执行完毕，若不再被其他单元使用则随即释放。

`start()` 抛出时，它启动的一切都已停止，仍被其他运行中单元使用的除外。以 `X → A、B`、
`A → C`、`B → C`、`B` 失败为例：

```
C.start → A.start → B.start ✗ → B.stop → A.stop → C.stop → start() 抛出 B 的异常
```

回滚中 `@stop` 抛出的异常作为 note 附在最初那个异常上。调用方取消 `start()` 时，同样的回滚
在取消传播之前完成；取消无法携带 `@stop` 的异常，因此它们交给事件循环的异常处理器。

**多个单元同时失败。** 一个失败不会取消其他单元。多个单元失败时合并为一个
`ExceptionGroup`；只有一个失败时原样抛出，经多条路径到达的同一个失败只报告一次。

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

rollback = Phase("rollback")
migrate = Phase("migrate", after=init, undo=rollback)


class Schema(Canary):
    @migrate
    async def apply(self) -> None: ...

    @rollback
    async def revert(self) -> None: ...


await unit.init()
await advance(unit, migrate)
```

`after` 声明前驱：前驱阶段尚未完成时推进本阶段会抛 `LifecycleError`，而不是静默跳过。

`undo` 声明撤销本阶段的阶段，与 `stop` 撤销 `start` 完全相同：`@migrate` 失败的单元立即执行
它的 `@rollback`，失败的推进释放它为此启动的一切。撤销全部已迁移的单元：

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
