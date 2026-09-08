# 生命周期

`Canary` 驱动每个单元走过一条显式的、异步原生的时间线。

## 五个时刻

框架把"一个单元从无到有再到销毁"分成五个时刻。判据只有一条：**每个时刻手上有什么**。

| 时刻 | 谁在动 | 手上有什么 |
|---|---|---|
| 构造 | 使用者的 `__init__` | 什么都没有（无参构造） |
| **装配** | **框架** | 建图 → 校验 → 排序 → 注入 |
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

| 方法 | 迁移 | 做什么 |
|---|---|---|
| `await app.init()` | `NEW → INITIALIZED` | 建图、校验、拓扑排序、**注入依赖**、按序执行 `@on_init` |
| `await app.start()` | `INITIALIZED → STARTED` | 按序执行 `@on_start`，随后合并所有 `@web_cocoa` 单元的路由 |
| `await app.stop()` | 任何终态 `→ STOPPED` | 逆序执行 `@on_stop` |

一句话概括：**`init` 把图装配好，让每个单元处于可用状态；`start` 让它们开始干活。**

## 状态机

```
NEW ─▶ INITIALIZING ─▶ INITIALIZED ─▶ STARTING ─▶ STARTED ─▶ STOPPING ─▶ STOPPED
        │                            │                    │
        └───────────────▶ FAILED ◀───┴────────────────────┘
```

`app.state` 返回当前的 `LifecycleState`。非法迁移抛 `LifecycleError`：

```python
await app.init()
await app.start()
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

**`init()` 失败不回滚。** 此时还没有任何 `@on_start` 跑过，也就没有资源需要回收。状态置为
`FAILED`，异常原样抛出。

**`start()` 失败全部回滚。** 不变式是「要么全部启动，要么什么都没启动」。任一环节抛出时，
已经**进入**过 `@on_start` 的单元（含失败的那一个）会按逆序执行 `@on_stop`，然后原样抛出
最初的异常；回收过程中的异常作为 note 附在它上面，不改变异常类型。

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

## ASGI 服务下

`Canary` 本身就是 ASGI 应用。在 uvicorn 之类的服务器下，`lifespan` 协议驱动同一套生命
周期：`lifespan.startup` 执行 `init()` + `start()`，`lifespan.shutdown` 执行 `stop()`。
启动失败会**如实汇报再抛出**（`lifespan.startup.failed`），不会让调用方以为启动成功。

没有 lifespan 时（比如直接把 `app` 当函数调），第一个请求会顺手把应用启起来。并发的首批
请求会排队等同一次启动，不会各自启动或撞上一个还没建好的入口。

## 两个环境变量

框架自己只有两个开关，直接读环境变量：

| 变量 | 作用 |
|---|---|
| `CANARY_LOG_LEVEL` | 设置 `canary` 这一棵 logger 的级别。不装 handler、不设 format、不碰 root。设成 `DEBUG` 会打印装配摘要（启动顺序、依赖、路由）。 |
| `CANARY_SLOW_CALLBACK_SECONDS` | 打开事件循环延迟探针：任何一次占用事件循环超过该秒数的回调都会被 asyncio 记一条 WARNING。它会打开 asyncio 的调试模式，有额外开销，属于开发期工具，默认关闭。 |

框架不提供配置机制 —— 配置就是你自己的一个 `@cocoa` 单元，日志就是标准库的
`logging.getLogger(__name__)`。
