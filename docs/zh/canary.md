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

## 生命周期方法

| 方法 | 状态迁移 | 作用 |
|---|---|---|
| `await app.init()` | `NEW → INITIALIZED` | 建图、拓扑排序、按序执行 `@on_init` |
| `await app.start()` | `INITIALIZED → STARTED` | 注入依赖、按序执行 `@on_start`、合并所有 `@web_cocoa` 单元的路由为统一服务入口 |
| `await app.stop()` | `STARTED → STOPPED` | 逆序执行 `@on_stop` |

引擎是异步原生的：钩子可同步可异步，运行时按返回值判断是否 `await`。状态机与错误处理见
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
await app.start()

# 仅数据层，独立启动
books = Canary(BookRepository)
await books.start()
```

依赖在单张图内共享，但在两个独立的 `Canary` 实例之间不共享。

## 服务 ASGI

`Canary` 本身就是一个 ASGI 应用。它的 `__call__(scope, receive, send)` 处理 `lifespan`
scope 以驱动 `init()` / `start()` / `stop()`，并把其余 scope（`http`、`websocket`、…）委托
给所有 `@web_cocoa` 单元合并出的**统一服务入口**。

这正是 [web 扩展](web.md) 的工作方式：每个 `@web_cocoa` 单元在 `@on_start` 阶段存储路由
条目；`Canary` 把它们合并成**一个** Starlette 应用，只挂一份 `/openapi.json` / `/docs` /
`/redoc`。web 扩展的 import 是**延迟**的 —— 只有真的存在路由条目时才会发生，所以纯
`@cocoa` 编排无需安装 `canary-framework[web]`：

```python
from canary_framework import Canary

app = Canary(LibraryAPI)  # app 本身就是 ASGI 应用

# uvicorn examples.library.web:app
```

路由合并与延迟加载的接线方式见 [架构](architecture.md)。
