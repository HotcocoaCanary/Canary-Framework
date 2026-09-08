# 020：`async def` 强制只看 handler 签名，迁移后最常见的阻塞写法照样放行

> | 归因 | **框架 70% / 生态 30%** |
> |---|---|
> | 可直接开 issue | ⚠️ 可以，但更像设计讨论而非 bug |
> | 框架侧改动点 | `web/infra/checks.py` 的适用范围；或新增一个开发期的事件循环延迟探针 |
> | 复现依赖 | 零业务代码，30 行 + 一次测量 |
> | 业务侧责任 | 无 |

- **类型**：设计反馈（P1）
- **影响版本**：canary-framework 0.9.3
- **发现场景**：场景一。这是作者点名想听的三件事之一，所以我们把实验重做了一遍。

## 结论先行

**这条规则挡住的不是最常见的那一种阻塞，而是最容易检测的那一种。**

发布说明用「10 个 100ms 的同步端点并发时，一个毫不相干的异步 `/health`
端到端从 0.6ms 涨到 1005ms」论证为什么要在声明处拒绝。我们用同一个实验测了三种形状：

```
10 个 100ms 的 /slow 并发，同时打一次 /health

形状                                       总耗时       /health 端到端
async def + 同步调用（迁移后最常见）        1018.8ms         1018.8ms
async def + asyncio.to_thread              103.7ms           14.1ms
真异步 I/O                                 102.4ms           12.7ms
```

第一行——签名是 `async def`、函数体里还是 `sqlite3` / `requests` / `psycopg2`——
复现出的数字和发布说明里的同步 handler **完全一样**，而框架完全不拦。

复现脚本：`apps/library/tests/test_framework_boundaries.py::test_an_async_handler_with_a_sync_body_stalls_the_loop_just_as_badly`

## 规则的覆盖面

`require_async` 只在两个地方被调用：`@get/@post/@route` 与 `@on_request_error`。
按发布说明给出的理由（"阻塞的不是它自己那个请求，而是整个进程"），
下面这些同样成立，但都不受检查：

| 位置 | 同步会阻塞整个进程吗 | 框架是否拒绝 |
|---|---|---|
| `@get` handler 签名 | 是 | ✅ 拒绝 |
| handler **调用的**仓储 / 服务方法 | 是 | ❌ 放行 |
| `@on_start` / `@on_stop` 钩子 | 是（阻塞启动与关停） | ❌ 放行（`_invoke_hook` 按返回值判断，同步就直接调） |
| `@cocoa` 单元的 `__init__` | 是 | ❌ 放行 |

第三行值得单独说：一个守护进程里 `@on_start` 做同步 DNS 解析 / 同步建连，
会让整个启动序列串行阻塞在事件循环上；而框架对钩子是明确**支持同步**的
（`_invoke_hook` 的 docstring 说"按返回值判断（而非函数声明）更稳健"）。
所以框架在 handler 上说"我们绝不偷偷 offload，同步就拒绝"，
在钩子上说"同步异步都行，我帮你判断"。同一个进程、同一条事件循环，两套态度。

## 这条规则值不值得留

值得。它确实消灭了一类真实缺陷，而且拒绝的时机极好——
不过要更正发布说明的一处措辞：拒绝发生在 **`@get` 求值那一刻，也就是 import 时**，
不是"装配期"。这对使用者更好（错误离现场最近），但它的副作用是
**一个同步 handler 会让整个模块 import 失败**，
连带 pytest 的 collection error，而不是某一个用例失败。写进文档比较好。

我们的迁移成本：**0 处**。场景一的 28 个端点在 0.9.2 时就全是 `async def`
（驱动是 asyncpg / aiosqlite / httpx），场景二没有 web 面。
换句话说，这条破坏性变更对一个**已经是全异步**的项目零成本，
对一个**部分同步**的项目则是一次全量改签名——而改完之后，
真正的阻塞问题一个都没解决，只是从签名挪进了函数体。
这正是我们担心的那个结果：这条规则最可能的实际效果，
是把一个**可见**的问题（同步签名）换成一个**不可见**的问题（同步函数体）。

## 建议

不是让框架去猜函数体里有什么——那既做不到也不该做。三条更实际的：

1. **把检查扩到钩子上**，或者明确说明为什么钩子不适用。
   现状的不一致本身会让使用者以为"框架管着这件事"，从而放松警惕。
2. **提供开发期的事件循环延迟探针**。标准库已经有了：

   ```python
   loop.set_debug(True)
   loop.slow_callback_duration = 0.05
   ```

   实测这能抓到上面第一行的形状：

   ```
   WARNING:asyncio:Executing <Task ...> took 0.202 seconds
   ```

   建议由 `CanaryConfig` 暴露成 `CANARY_SLOW_CALLBACK_SECONDS`，
   在 `_apply_framework_config()` 里应用。这条比签名检查有价值得多：
   它抓的是**实际发生的阻塞**，不管它藏在哪一层。
   拒绝同步签名是编译期检查，这个是运行期检查，两者互补。
3. **文档里把 `asyncio.to_thread` 的位置写清楚**。发布说明里那行
   `row = await asyncio.to_thread(self.repo.query_sync, 42)` 写在 handler 里，
   但正确的位置几乎总是**仓储内部**——否则每个调用点都要记得包一层。
   我们的写法是让仓储方法自己是 `async def` 且内部 `to_thread`，
   这样调用方不必知道底层是不是阻塞的。

## 回归测试

`apps/library/tests/test_framework_boundaries.py::test_an_async_handler_with_a_sync_body_stalls_the_loop_just_as_badly`
`apps/library/tests/test_framework_boundaries.py::test_a_sync_handler_is_refused_at_declaration_time`
`apps/library/tests/test_framework_boundaries.py::test_async_handlers_no_longer_serialise_the_process`
