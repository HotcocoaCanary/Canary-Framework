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
的依赖图合并为一张共享图。`Canary(...)` 本身不做任何事 —— 建图发生在 `init()`。

## 生命周期方法

| 方法 | 状态迁移 | 作用 |
|---|---|---|
| `await app.init()` | `NEW → INITIALIZED` | 建图、校验、拓扑排序、**注入依赖**、按序执行 `@on_init` |
| `await app.start()` | `INITIALIZED → STARTED` | 按序执行 `@on_start`，随后合并所有 `@web_cocoa` 单元的路由为统一服务入口 |
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
启动顺序、每个单元的依赖、挂了哪些路由。排查"为什么这条路由不在"或"为什么这个单元先
启动"时不必去读框架源码：

```text
Canary assembled 4 unit(s)
  roots: LibraryApp
  start order (stop runs in reverse):
    1. Config
    2. Database  <- Config
    3. BookRepository  <- Database
    4. LibraryApp  <- BookRepository
  routes:
    GET    /api/books  -> LibraryApp.list_books
```

## 服务 ASGI

`Canary` 本身就是一个 ASGI 应用。它的 `__call__(scope, receive, send)` 处理 `lifespan`
scope 以驱动 `init()` / `start()` / `stop()`，并把其余 scope（`http`、`websocket`、…）委托
给所有 `@web_cocoa` 单元合并出的**统一服务入口**：

```python
from canary_framework import Canary

app = Canary(LibraryAPI)  # app 本身就是 ASGI 应用

# uvicorn examples.library.web:app
```

整个编排只挂一份 `/openapi.json` 与 `/docs`。web 扩展的 import 是**延迟**的 —— 只有图上真
存在 `@web_cocoa` 单元时才会发生，所以纯 `@cocoa` 编排无需安装 `canary-framework[web]`。

没有 lifespan 时（比如直接把 `app` 当函数调用），第一个请求会顺手把应用启起来；并发的
首批请求会排队等同一次启动。这条路径只是兜底，正式部署请交给服务器的 lifespan。

路由合并与延迟加载的接线方式见 [架构](architecture.md)。
