# 0.9.3 新特性

0.9.3 是一次**收敛**：把这个框架收回到它真正差异化的那一件事上 —— **依赖装配与生命周期** ——
并把失败路径补完整。它包含多处破坏性变更，其中最大的一条是删掉了整个 web 扩展。

## 它现在是什么

> **Canary 是一个运行时容器，不是 web 框架。**

它负责把一堆对象按依赖关系装配起来、按序启动、按逆序回收。至于这些对象最后被什么外壳
驱动 —— HTTP、CLI、定时任务、消息消费者 —— 那是外壳的事。

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with canary:          # 这就是全部的接线
        yield


app = FastAPI(lifespan=lifespan)
```

## 一条贯穿全框架的规则

> **框架只造空壳，一切需要外界输入的事都在生命周期里做。**

图上的实例**全部由框架无参构造**，没有第二条来源。这不是限制：构造函数没有对手
（`@on_start` 有 `@on_stop` 配对，"构造"却没有"析构"），把需要输入的事推迟到生命周期里，
等于让每一件事都落进一个有台账、能逆序回收的阶段。

## 删除 `canary_framework.web`

**这是这一版最大的变化。** web 扩展（`@web_cocoa` + 路由装饰器 + 参数绑定 + OpenAPI，
约 1300 行）整个删掉了，连同 `Canary` 的 ASGI 面（`__call__`、lifespan 协议、冷启动、
路由收集，约 100 行）。

理由不是它做得不好 —— 它的请求路径实测比 FastAPI 快 2.4–3.3 倍。理由是**它做的不是我们
该做的事**：

- 它和 FastAPI / Starlette 做同一件事，而那不是这个框架的差异化所在。
- 一旦走上这条路，就得在 WebSocket、文件上传、中间件、认证这些方向上永远追赶。
- 它占了框架一半以上的代码，却贡献了绝大多数的 bug。

而且**它想保住的那个好处并不需要它**：路由是"已注入依赖的单元上的方法"，这一点直接把
绑定方法交给 FastAPI 就有了 —— 绑定方法的签名里没有 `self`，FastAPI 照常做参数绑定、
校验和文档，而 `self.repo` 因为实例是 Canary 装配的，本来就在。

```python
unit = canary[LibraryApi]                       # 普通 @cocoa，零 web 标记
app.get("/books/{book_id}")(unit.get_book)      # FastAPI 全都认
```

框架因此从 2300 行降到 **842 行**，而且剩下的每一行都在做依赖装配和生命周期。

## 新增

- **装配移进构造函数；四个动作一一对应。** `Canary(Root)` 一返回，图已经建好、排好序、
  依赖已注入 —— `canary[SomeUnit]` 立刻可用，装配期错误在这一行抛出。这是在守框架自己给
  单元定的规矩（"构造完就必须可用"）：运行时没有理由例外。

  之后三个动作各对应一个钩子阶段，**没有一个方法做两件事**：`init()` 只跑 `@on_init`
  （各就各位），`start()` 只跑 `@on_start`（开工），`stop()` 只跑 `@on_stop`（回收）。
  `init()` 和 `start()` 之间的栅栏就是两个方法的边界。忘了 `init()` 是响的：
  `LifecycleError: call init() before start()`。

  状态起点从 `NEW` 改名 `READY` —— 一个刚造出来、已经能取实例的运行时叫 "NEW" 会掩盖掉
  刚做成的事。

- **并发启动。** `Canary(Root, start_concurrency=8)` 让互不依赖的单元同时启动，带并发上限。
  IO 密集的图上 7.1x，典型 web 形状 1.7x，一条链 1.0x —— 由图的形状决定。默认关着（连接
  风暴、兄弟顺序）；顺序启动时装配摘要会算出关键路径、告诉你开了能省多少。失败语义与顺序
  启动一致：单个失败原样抛出，被取消的单元照样回收。

- **`Canary.lifespan`** —— 交给宿主的入口，一行接进任何主流框架：

  ```python
  app = FastAPI(lifespan=canary.lifespan)
  app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
  server = MCPServer("demo", lifespan=canary.lifespan)
  ```

  Python 世界的宿主只有两种形状——收异步上下文管理器，或收成对的启动/关停回调——两种现在
  都直接支持。`lifespan` 与 `async with canary` 只差交出什么：前者交出 `None`（ASGI 协议
  把交出值当作要合并进 `scope["state"]` 的映射，交出容器会漏出一个毫无线索的 `KeyError`），
  后者交出容器自己。

- **注入提前到 `init()`。** `@on_init` 因此第一次有了独立含义 —— "依赖已就位，但还没有
  任何东西开始运行"。装配类的错误也在装配阶段就暴露。
- **`ConstructionError`** —— 需要构造参数的单元给出可操作的错误，而不是裸 `TypeError`，
  并说清唯一的出路：把构造参数变成依赖。
- **`InjectionError`** —— 两个依赖的 snake_case 撞名不再"后写的赢"。
- **装配摘要** —— `CANARY_LOG_LEVEL=DEBUG` 时在启动末尾打印启动顺序与依赖。
- **`CANARY_SLOW_CALLBACK_SECONDS`** —— 可选的事件循环延迟探针，抓 `async def` 函数体里
  的同步阻塞；`stop()` 时还原，不污染同进程后续代码。

## 变更（破坏性）

- **删除 `canary_framework.web` 与 `Canary` 的 ASGI 面**（见上）。`Canary` 不再是 ASGI
  应用；接进宿主用 `async with canary:`。
- **删除 `Canary(provide=...)`。** 它与"单元必须能无参构造"这条规则互相咬。测试里替换
  依赖直接给属性赋值即可（`svc.database = FakeDb()`）—— 注入本来就只是 setattr。
- **`stop()` 是唯一的回收路径。** 从任何终态都能调用，重复调用是幂等的 —— `finally:
  await app.stop()` 永远安全。

## 修复

- **`start()` 失败会漏掉已启动的单元。** 现在按台账逆序回收（含失败的那一个），再原样
  抛出最初的异常。
- **一个 `@on_stop` 抛出会中断整个关停。** 现在收集异常继续回收，最后抛 `ExceptionGroup`。
- **近千节的依赖链会撞 `RecursionError`。** 依赖链的深度是使用者的数据，不该受 Python
  递归上限约束。建图改成显式栈，现在 50000 节照常。
- **慢回调探针看不见启动期。** asyncio 在回调开始执行前就读了 debug 标志，而探针是在
  那个回调执行到一半时才打开的。

## 性能

```
1000 单元建图 + 注入 + @on_init    37.7ms → 2.4ms      15.6x
MRO 扫描（5000 单元自身时间）        55ms  → 5ms        11x
框架自身模块的导入耗时                              0.0ms
1000 单元的图                                    约 3.9 MiB
```

那 15.6 倍来自一处顺序错误：`inspect.signature` 站在**成功路径**上，而它只为了在失败时
说清楚话。改成先构造、出了 `TypeError` 再回头看签名。

## 零依赖

`pip install canary-framework` 不拉进任何第三方包，只用标准库。这条有测试守着：跑完一整轮
生命周期后，`sys.modules` 里不该出现任何来自 site-packages 的东西。
