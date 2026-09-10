# 生命周期

`Canary` 驱动每个单元走过一条显式的、异步原生的时间线。

## 五个时刻

框架把"一个单元从无到有再到销毁"分成五个时刻。判据只有一条：**每个时刻手上有什么**。

| 时刻 | 谁在动 | 手上有什么 |
|---|---|---|
| 构造 | 使用者的 `__init__` | 什么都没有（无参构造） |
| **装配** | **框架**，在 `Canary(...)` 里 | 建图 → 校验 → 排序 → 注入 |
| 初始化 `@on_init` | 使用者 | 依赖已就位，但还没有任何东西开始运行 |
| 启动 `@on_start` | 使用者 | 依赖已就位，可以获取资源 |
| 停止 `@on_stop` | 使用者 | 逆序回收 |

中间那一步是**框架的动作，不是使用者的钩子** —— 这正是它不需要一个钩子的原因：在装配的
任何一个瞬间，使用者能拿到的东西都不比前后两个时刻更多。

## 三个钩子

| 声明 | 执行于 | 顺序 |
|---|---|---|
| `@on_init` | `init()`，注入之后 | 拓扑序（依赖在前） |
| `@on_start` | `start()` | 拓扑序（依赖在前） |
| `@on_stop` | `stop()` | 逆拓扑序（被依赖方在前） |

所有钩子都可选。钩子可以是普通函数或协程函数 —— 运行时检查返回值，仅当可等待时才
`await`，因此同步与异步钩子可自由混用。

## 三个方法各做什么

| 何时 | 迁移 | 做什么 |
|---|---|---|
| `Canary(*roots)` | —— `→ READY` | 装配：建图、校验、拓扑排序、**注入依赖**。同步，不跑任何钩子 |
| `await app.init()` | `READY → INITIALIZED` | 各就各位：全部 `@on_init` |
| `await app.start()` | `INITIALIZED → STARTED` | 开工：全部 `@on_start`，进入即记账 |
| `await app.stop()` | 任何终态 `→ STOPPED` | 逆序执行 `@on_stop` |

四个动作，四个含义，一一对应：**构造装配、`init` 各就各位、`start` 开工、`stop` 回收。**
没有一个方法做两件事。`init()` 和 `start()` 之间是一道栅栏 —— 整张图各就各位之后，才允许
任何单元开工；这道栅栏就是两个方法的边界，不调 `start()`，谁也不会开工。

## 状态机

```
READY ─▶ INITIALIZING ─▶ INITIALIZED ─▶ STARTING ─▶ STARTED ─▶ STOPPING ─▶ STOPPED
             │                            │                       │
             └──────────────▶ FAILED ◀────┴───────────────────────┘
```

三个动作各有一个进行中的状态（`*ING`），它们只可能被并发调用者观察到。

起点是 `READY` 而不是"什么都还没做"：装配在构造函数里已经完成，一个刚造出来的运行时
**已经可用** —— `canary[SomeUnit]` 立刻能取到已注入依赖的实例，只是还没有人开始运行。

`app.state` 返回当前的 `LifecycleState`。非法迁移抛 `LifecycleError`：

```python
await app.init()
await app.start()
await app.init()
await app.start()  # LifecycleError: illegal transition from STARTED
```

## 钩子顺序

对于图 `APIService → UserService → Database`（箭头 = "依赖"）：

- **初始化** — `Database` → `UserService` → `APIService`
- **启动** — `Database` → `UserService` → `APIService`
- **停止** — `APIService` → `UserService` → `Database`

每个单元都在其依赖之后才初始化、启动；在依赖之前停止。顺序来自卡恩拓扑排序，因而是确定
的。

## 钩子可叠加

一个标记可被多个方法共享 —— 混入的钩子先于本类执行，按定义顺序：

```python
class LoggingMixin:
    @on_start
    def log_start(self) -> None:
        print(f"[{type(self).__name__}] starting")


@cocoa(deps=[Config])
class Database(LoggingMixin):
    @on_start
    async def connect(self) -> None:
        await self.pool.connect()
```

`log_start`（混入）与 `connect`（本类）都会执行，且按此顺序。

## 失败路径

失败路径是这个框架有意设计过的部分，三条规则各自不同：

**只有一条规则：`stop()` 收台账里的一切。** `init()` 阶段失败时台账是空的（`@on_init`
按契约不获取资源），所以没有东西要收，状态直接置 `FAILED`。

台账记的是**进入过 `@on_start`** 的单元。`@on_start` 按契约是唯一获取资源的地方，所以
只有它需要对应的回收。

`start()` 失败时不变式是「要么全部启动，要么什么都没启动」：台账里的单元（含失败的那一个）
按逆序执行 `@on_stop`，然后原样抛出最初的异常；回收过程中的异常作为 note 附在它上面，
不改变异常类型。

`@on_init` 阶段失败时台账还是空的，回滚自然是空转 —— 不需要为它单写一条规则。

**`stop()` 是唯一的回收路径。** 它同时承接正常结束与失败结束：

```python
app = Canary(Root)
try:
    await app.init()
    await app.start()
finally:
    await app.stop()   # 从 STARTED 可调，从 FAILED 也可调；重复调用是幂等的
```

没启动过就调用 `stop()` 不是错误 —— 它空转并进入 `STOPPED`（先前的 `FAILED` 不会被抹掉）。
这样 `finally: await app.stop()` 永远是安全的写法，不必先判断状态。

单个 `@on_stop` 抛出不会中断回收：异常被逐一收集，其余单元照常回收，最后合并成一个
`ExceptionGroup` 抛出。

## 并发启动

```python
Canary(Root, start_concurrency=8)
```

默认 `None`：严格按拓扑序一个一个启动。给一个正整数，**互不依赖的单元同时启动**，同时最多
这么多个。加速比 = 顺序总耗时 ÷ 关键路径（按耗时算最长的一条依赖链），完全由图的形状决定：

```
50 个各 60ms 的独立 IO 单元    3009ms → 423ms     7.1x
典型 web 形状（DB / Redis / MQ）  260ms → 152ms     1.7x
一条链                            无变化            1.0x
```

**默认关着**，两个理由：并发启动会同时向下游发起 N 个连接（连接风暴 —— 实测 20 个单元
对一个"最多接 8 个连接"的下游，12 次被拒、启动失败）；它也会打破"兄弟按声明序启动"这个
虽然从未承诺、但可能有人依赖的顺序。

**上限不是可选参数。** 信号量只圈住真正跑钩子的那段，等依赖的时候不占名额。调度按依赖
驱动 —— 每个单元等自己的依赖，不按拓扑层次分组（分组会让一个单元白等同层里最慢的那个）。

**失败语义与顺序启动一致。** 一个单元失败时同批的其它单元被取消；被取消的单元同样持有半个
资源，同样进了台账、同样被回收。只有一个真实失败时原样抛出（`except RuntimeError` 照旧管用）；
多个单元同时失败才抛 `ExceptionGroup`，一个都不隐瞒。

**不知道该不该开？框架会自己告诉你。** `CANARY_LOG_LEVEL=DEBUG` 时，顺序启动的装配摘要会
记下每个单元的耗时、算出关键路径，并说明开并发能省多少：

```
Canary assembled 8 unit(s), started in 260ms
  ...
  critical path is 150ms of the 260ms spent starting units
  start_concurrency=3 could bring that down to about 150ms (1.7x)
```

耗时太短或图太窄时它不吭声。

## 交给宿主驱动

两种宿主协议，两个入口：

| 宿主收什么 | 用哪个 | 谁是这样 |
|---|---|---|
| 一个异步上下文管理器 `Callable[[Host], AsyncContextManager]` | `canary.lifespan` | ASGI（Starlette / FastAPI / Litestar）、MCP、FastStream |
| 成对的启动 / 关停回调 | `start()` 与 `stop()` | Quart、Sanic、arq、Dramatiq |

```python
app = FastAPI(lifespan=canary.lifespan)          # 就这一行
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
server = MCPServer("demo", lifespan=canary.lifespan)
```

没有宿主时（CLI、脚本、测试夹具）直接用：

```python
async with canary.lifespan():
    ...
```

框架不认识任何具体宿主 —— 上面那张表覆盖的是 Python 世界仅有的两种形状。

`canary.lifespan` 和 `async with canary` 只差一件事：**它交出 `None` 而不是容器自己**。
ASGI 的 lifespan 协议会把交出来的值当作要合并进 `scope["state"]` 的映射，交出容器会让
Starlette 去 `dict.update(canary)`，漏出一个毫无线索的 `KeyError`。`async with canary`
服务的是你自己的代码，照常交出容器。

## 两个环境变量

框架自己只有两个开关，直接读环境变量：

| 变量 | 作用 |
|---|---|
| `CANARY_LOG_LEVEL` | 设置 `canary` 这一棵 logger 的级别。不装 handler、不设 format、不碰 root。设成 `DEBUG` 会打印装配摘要（启动顺序、依赖、路由）。 |
| `CANARY_SLOW_CALLBACK_SECONDS` | 打开事件循环延迟探针：任何一次占用事件循环超过该秒数的回调都会被 asyncio 记一条 WARNING。它会打开 asyncio 的调试模式，有额外开销，属于开发期工具，默认关闭。 |

框架不提供配置机制 —— 配置就是你自己的一个 `@cocoa` 单元，日志就是标准库的
`logging.getLogger(__name__)`。
