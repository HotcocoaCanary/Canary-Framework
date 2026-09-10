# 0.9.3 新特性

0.9.3 含多处破坏性变更；0.9.x 仍在快速定型阶段。

## 生命周期

四个动作，每个只跑一个阶段：

```python
canary = Canary(Root)      # 装配：建图、排序、注入依赖。同步，不跑任何钩子
await canary.init()        # 全部 @on_init
await canary.start()       # 全部 @on_start
await canary.stop()        # 逆序全部 @on_stop
```

- **装配移进构造函数。** `Canary(Root)` 返回时图已建好、排好序、依赖已注入，
  `canary[SomeUnit]` 立即可用；装配类错误（`ConstructionError`、`InjectionError`、
  `CircularDependencyError`、非 cocoa 的 `TypeError`）在这一行抛出。
- **`init()` 只跑 `@on_init`，`start()` 只跑 `@on_start`。** 两者之间是一道栅栏：全部
  `@on_init` 完成后才允许任何 `@on_start`。未 `init()` 就 `start()` 抛
  `LifecycleError: call init() before start()`。
- **`stop()` 是唯一的回收路径**，从 `STARTED` 和 `FAILED` 都可调用，重复调用幂等，
  从未启动时空转。失败规则只有一条：`stop()` 收台账里的一切。
- **状态起点为 `READY`**（此前为 `NEW`）。

## 并发启动

```python
Canary(Root, start_concurrency=8)
```

互不依赖的单元同时启动，同时最多 N 个。调度按依赖驱动，耗时贴着关键路径。默认 `None`
（严格顺序）。失败语义与顺序启动一致：单个失败原样抛出，多个同时失败合成 `ExceptionGroup`，
被取消的单元照常回收。

顺序启动时，`CANARY_LOG_LEVEL=DEBUG` 的装配摘要会记录逐单元耗时、算出关键路径，并给出
`start_concurrency` 建议值。

## 接入宿主

```python
app = FastAPI(lifespan=canary.lifespan)              # ASGI、MCP、FastStream
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
async with canary.lifespan(): ...                    # 无宿主
```

收成对启停回调的宿主（Quart、Sanic、arq、Dramatiq）用 `init()` / `start()` 与 `stop()`。

## 新增

- `ConstructionError` —— 单元需要构造参数时给出可操作的错误，而不是裸 `TypeError`。
- `InjectionError` —— 两个依赖的 snake_case 撞名时抛出，而不是后写的覆盖先写的。
- 装配摘要 —— `CANARY_LOG_LEVEL=DEBUG` 时在启动末尾打印启动顺序、逐单元依赖与耗时。
- `CANARY_SLOW_CALLBACK_SECONDS` —— 事件循环延迟探针，抓 `async def` 函数体里的同步阻塞；
  `stop()` 时还原。

## 移除

- `canary_framework.web` 扩展，以及 `Canary` 的 ASGI 面（`__call__`、lifespan 协议、
  冷启动、路由收集）。`Canary` 不再是 ASGI 应用。
- `Canary(provide=...)` 与 `ProvisionError`。测试中替换依赖直接给属性赋值即可。
- `[web]` 与 `[test]` 两个可选依赖组。

## 修复

- `start()` 失败会漏掉已启动的单元 —— 现在按台账逆序回收，再原样抛出最初的异常。
- 一个 `@on_stop` 抛出会中断整个关停 —— 现在收集异常继续回收，最后抛 `ExceptionGroup`。
- 近千节的依赖链撞 `RecursionError` —— 建图改为显式栈，50000 节可正常处理。
- 慢回调探针看不见启动期。

## 性能

```
1000 单元装配（建图 + 注入）        37.7ms → 2.4ms
MRO 扫描（5000 单元自身时间）        55ms  → 5ms
框架自身模块的导入耗时                             0.0ms
1000 单元的图常驻内存                          约 3.9 MiB
```

## 零依赖

`pip install canary-framework` 只用标准库。测试守着这条：跑完一整轮生命周期后
`sys.modules` 中不出现任何来自 site-packages 的模块。
