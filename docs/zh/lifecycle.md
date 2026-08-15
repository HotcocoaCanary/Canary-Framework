# 生命周期

`Canary` 驱动每个单元走过一个显式的、异步原生的生命周期。钩子用 `@on_init` / `@on_start` /
`@on_stop` 声明，按确定性顺序执行。

## 三个钩子

| 声明 | 执行于 | 顺序 |
|---|---|---|
| `@on_init` | `init()` | 拓扑序（依赖在前） |
| `@on_start` | `start()` | 拓扑序（依赖在前），注入之后 |
| `@on_stop` | `stop()` | 逆拓扑序（被依赖方在前） |

所有钩子都可选。钩子可以是普通函数或协程函数 —— 运行时检查返回值，仅当可等待时才
`await`，因此同步与异步钩子可自由混用。

## 状态机

每个 `Canary` 跟踪一个八态状态机：

```
NEW ─▶ INITIALIZING ─▶ INITIALIZED ─▶ STARTING ─▶ STARTED ─▶ STOPPING ─▶ STOPPED
        │                            │                    │
        └───────────────▶ FAILED ◀───┴────────────────────┘
```

`app.state` 返回当前的 `LifecycleState`。状态机保证生命周期操作按合法顺序执行：

```python
await app.stop()  # LifecycleError: illegal transition from NEW
await app.init()
await app.start()
await app.start()  # LifecycleError: illegal transition from STARTED
```

钩子抛异常会把状态置为 `FAILED` 并重新抛出该异常。

## 钩子顺序

对于图 `APIService → UserService → Database`（箭头 = “依赖”）：

- **初始化** — `Database` → `UserService` → `APIService`。
- **启动** — `Database` → `UserService` → `APIService`。
- **停止** — `APIService` → `UserService` → `Database`。

每个单元都在其依赖之后才初始化、启动；在依赖之前停止。顺序来自卡恩拓扑排序，因而是确定
的。

## 钩子可叠加

一个标记可被多个方法共享 —— 混入的钩子先于本类执行，按定义顺序。这让混入类能添加
`@on_start` 行为而不覆盖本类的：

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

## 失败处理

钩子异常会从 `init()` / `start()` / `stop()` 传播出去，运行时先把状态置为 `FAILED`。
运行时**不**做自动回滚 —— 当部分清理很重要时，请在自己的 `@on_stop` 钩子里实现回滚。

## ASGI 服务下

当 `Canary` 通过 ASGI（如 uvicorn）提供服务时，`lifespan` 协议驱动同一套生命周期：
`lifespan.startup` 执行 `init()` + `start()`，`lifespan.shutdown` 执行 `stop()`。显式调用与
服务器路径共用同一引擎。
