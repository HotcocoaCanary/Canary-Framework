# 运行时（Canary）

`Canary` 是持有整张 [cocoa](cocoa.md) 依赖图并驱动其生命周期的编排器。它本身不是业务单元
—— 只负责解析、排序与运行。

```python
from canary_framework import Canary


app = Canary(UserService)
await app.init()
await app.start()
...
await app.stop()
```

## 构造

```python
app = Canary(*roots)
```

每个根都必须被 `@cocoa` 标记，否则 `Canary` 在构造时抛出 `TypeError`。传入多个根会把它们
的依赖图合并为一张共享图。

**构造即装配**：`Canary(...)` 一返回，图已经建好、排好序、依赖已注入 —— `canary[SomeUnit]`
立刻能用。装配是同步的，不需要事件循环；装配类的错误也在这一行抛出。

## 装配与生命周期

| 何时 | 状态迁移 | 作用 |
|---|---|---|
| `Canary(*roots)` | —— `→ READY` | 装配：建图、校验、拓扑排序、**注入依赖**。同步，不跑任何钩子 |
| `await app.init()` | `READY → INITIALIZED` | 各就各位：全部 `@on_init` |
| `await app.start()` | `INITIALIZED → STARTED` | 开工：全部 `@on_start`，进入即记账 |
| `await app.stop()` | 任何终态 `→ STOPPED` | 逆序执行 `@on_stop`；幂等，正常结束与失败结束共用 |

引擎是异步原生的：钩子可同步可异步，运行时按返回值判断是否 `await`。状态机与失败路径见
[生命周期](lifecycle.md)。

`Canary` 也实现了异步上下文管理器协议：

```python
async with Canary(UserService) as app:
    assert app[Database] is app[UserService].database
```

## 访问实例

用 `__getitem__` 获取图中某类型的共享单例：

```python
users = app[UserService]
assert users.database is app[Database]
```

`order` 属性返回拓扑启动顺序（依赖在前）；`instances` 按同序返回对应实例；`state` 返回
当前的 `LifecycleState`。

## 多根编排

因为 `Canary` 接受多个根，同一个单元可以参与不同的图 —— 任意子图也能独立启动：

```python
# 完整应用
app = Canary(LibraryApp)
await app.init()
await app.start()

# 仅数据层，独立启动
books = Canary(BookRepository)
await books.init()
await books.start()
```

依赖在单张图内共享，但在两个独立的 `Canary` 实例之间不共享。

多根还有一个后果值得知道：**没有任何单元最后启动**，所以不存在"一切都起来之后"那个位置。
需要那个位置的话，声明一个组合根。

## 装配摘要

把 `CANARY_LOG_LEVEL` 设成 `DEBUG`，启动末尾会在 `canary.runtime` 上打印一份摘要 ——
启动顺序、每个单元的依赖。排查"为什么这个单元先启动"时不必去读框架源码：

```text
Canary assembled 4 unit(s)
  roots: LibraryApp
  start order (stop runs in reverse):
    1. Config
    2. Database  <- Config
    3. BookRepository  <- Database
    4. LibraryApp  <- BookRepository
```

## 交给宿主驱动

`Canary` 不认识任何外壳 —— 它既不是 web 框架，也不是 CLI 框架。

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

需要在宿主的处理函数里拿到某个单元时，`canary[SomeUnit]` 就是它 —— 依赖已经注入好了，
`self.<dep>` 直接可用。配合 FastAPI 的 `Depends` 只要一个三行的工厂：

```python
def provide[T](cls: type[T]):
    def dep() -> T:
        return canary[cls]
    return dep


@app.get("/books/{book_id}")
async def read(book_id: int, svc: Annotated[LibraryApp, Depends(provide(LibraryApp))]):
    return svc.get_book(book_id)
```

HTTP、WebSocket、静态文件、中间件、认证全归宿主。Canary 只保证你的对象被正确装配、按序
启动、按逆序回收。
