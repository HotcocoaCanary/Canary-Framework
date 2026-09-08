# canary-framework 0.9.3 内测验证报告

> 验证方：canary-scenarios（两个形态刻意不同的真实项目）
> 框架版本：`release/0.9.3`（`f3492d6`），本地可编辑安装
> 验证日期：2026-09-04
> 结果：**两个场景全部迁移完成，142 个测试全绿**（0.9.2 时是 117 个）

| | 场景一 `apps/library` | 场景二 `apps/telemetry` |
|---|---|---|
| 形态 | 请求驱动的 HTTP API + RAG | 时间驱动的常驻守护进程 |
| 框架面 | core + web 扩展 | 纯 core（依赖里没有 `[web]`） |
| 测试 | 84 → **102** | 33 → **40** |

## 一句话结论

**0.9.3 兑现了它列出的每一条修复，我们因此删掉了四类绕行代码；
但三条新增能力各自带来一个新问题，其中一个是 P0 回归。**

删掉的绕行：

| 绕行 | 因为哪条修复 | 删掉了什么 |
|---|---|---|
| `guard()` —— 每个 handler 都要包一层的错误边界 | `@on_request_error` | 场景一 35 处调用点的错误分支，收敛成 2 个映射方法 |
| `R` 信封里自带 `code` 因为框架只会答 200 | Response 放行 + 异常映射 | 状态码回到状态行上（信封保留，那是前端契约） |
| `embedding_provider` / `chat_provider` / `clock_mode` / `source_mode` / `alert_sink` 五个「实现分支」配置开关 | `overrides=` | 5 个开关、5 处 `if`，换成 5 个独立的类 |
| 启动失败 / 关停失败的手写兜底 | 生命周期三条失败路径 | 场景二不再需要在 `@on_stop` 里自己 try/except |

新问题（详见 `doc/bug/`）：

| 编号 | 标题 | 级别 |
|---|---|---|
| [019](bug/019-lifespan-startup-failure-hangs-the-test-client.md) | lifespan 启动失败后 `return` 而不 `raise`，挂起被挪到 shutdown | **P0 回归** |
| [016](bug/016-annotation-declarations-fail-silently.md) | 类级注解解析失败时 `self.config` / `self.log` 被静默跳过 | **P0** |
| [015](bug/015-config-as-a-unit-collides-with-itself.md) | 配置类同时是 `@cocoa` 单元时装配被拒，升级第一堵墙 | P1 |
| [020](bug/020-the-async-rule-only-covers-the-handler-signature.md) | `async def` 强制只看签名，迁移后最常见的阻塞照样放行 | P1 |
| [017](bug/017-injected-config-is-not-reachable-from-the-runtime.md) | 注入的配置实例没有运行时入口 | P2 |
| [018](bug/018-a-substitute-with-deps-fails-with-a-bare-keyerror.md) | 带 `deps` 的替身抛裸 `KeyError` | P2 |
| [021](bug/021-substitution-and-injection-by-class-name-pull-apart.md) | 替换与「按类名注入」互相拉扯 | P3（设计讨论） |

---

## 作者点名想知道的三件事

### 一、`async def` 这条挡住了多少地方？

**挡住 0 处。但这个数字不说明这条规则没成本。**

场景一的 28 个端点在 0.9.2 时就已经全是 `async def`（驱动是 asyncpg / aiosqlite /
httpx），场景二没有 web 面。所以迁移成本是零——唯一被挡住的是我们**自己的边界测试**
里那个故意写成同步的 `/toy/slow`，它存在的目的正是钉住「框架不 offload」这个旧行为。

真正值得报告的是我们顺手做的对照实验（完整数据见 [020](bug/020-the-async-rule-only-covers-the-handler-signature.md)）：

```
10 个 100ms 的 /slow 并发，同时打一次 /health

async def + 同步调用（迁移后最常见）    /health 端到端 1018.8ms
async def + asyncio.to_thread                        14.1ms
真异步 I/O                                           12.7ms
```

第一行就是你在发布说明里担心的那件事，数字和你给的 1005ms 一致。
所以我们的判断是：**这条规则对已经全异步的项目零成本，对部分同步的项目则是
一次全量改签名，而改完之后阻塞一个都没少——只是从签名挪进了函数体。**

规则本身值得留（它消灭的那类缺陷是真的），但建议配一个运行期的探针：
`loop.set_debug(True)` + `slow_callback_duration`，由 `CANARY_SLOW_CALLBACK_SECONDS`
暴露出来。实测它能抓到上面第一行的形状。编译期检查抓签名，运行期探针抓实际阻塞，
两者互补——只有前者会给人一种"框架管着这件事"的错觉。

另外两条小的：

- 拒绝发生在 **import 时**（`@get` 求值那一刻），不是发布说明写的"装配期"。
  对使用者更好，但副作用是一个同步 handler 会让整个模块 import 失败，
  在 pytest 里表现为 collection error。建议写进文档。
- `@on_start` / `@on_stop` / 仓储方法**同步照样放行**（`_invoke_hook` 明确支持）。
  同一条事件循环上两套态度，建议要么扩到钩子、要么说明为什么不扩。

### 二、`@on_request_error` 的作用域（全应用）在我们的分层里够不够用？

**够用，而且我们认为全应用是对的。** 但有一处摩擦值得知道。

场景一的分层是 `router → service → repository`，领域异常
（`DomainError` 及其 4 个子类）由 service 抛出。0.9.3 之前每个 handler 都要
`await guard(...)` 包一层；现在整个应用只剩两个方法，都挂在组合根 `LibraryApi` 上：

```python
@on_request_error(DomainError)          # 一族领域异常，按 __mro__ 兜住 4 个子类
async def domain_error(self, request, exc) -> Response: ...

@on_request_error(RequestValidationError)   # 把内置 422 换成自家信封
async def malformed_request(self, request, exc) -> Response: ...
```

35 个 handler 的错误分支就此消失。**登记基类兜住一族**这个设计尤其好用——
我们的 `DomainError.code` 本来就带着该有的状态码，映射方法只有 6 行。

**摩擦点：作用域是全应用，但登记的位置是某一个单元。**
这两件事不一致。我们把它放在组合根上是因为那里最像"全局"，
但框架并不要求——任意一个 `@web_cocoa` 单元登记 `Exception` 就会静默接管整个应用的
500。在一个多人协作的代码库里，这是一条只在装配摘要里能看见的隐式全局状态。

建议：不必改语义，但**装配摘要里的 `error handlers:` 一节应该默认更容易看到**，
或者提供一个 `Canary.error_handlers` 只读入口，让 code review 能断言
"这个应用只登记了这几条"。我们现在是靠 `@on_request_error` 重复登记会在装配期报错
（这个检查很好）来兜底的，但它只能防冲突，防不了"某个模块偷偷登记了 `Exception`"。

至于**每条路由不同的映射**——我们同意那几乎总是 bug。没有需求。

### 三、`self.config` / `self.log` 的注解写法别扭吗？

**写法本身一点都不别扭，是这一版里手感最好的东西。** 问题全在它的失败模式上。

好的部分：

```python
@cocoa
class Repository:
    log: logging.Logger
    config: RepoConfig
```

- 声明即注入，mypy 认，读代码的人也认，比 `deps=[...]` 里塞一个配置类清楚得多；
- 配置整图共享一个实例、可被 `overrides` 替换、取值优先级交给 pydantic-settings——
  这三条我们都验证过，都对；
- 日志只决定 logger 名字（`模块.类名`），不装 handler、不碰 root。
  两个项目现有的 `logging.basicConfig` / `dictConfig` 完全不受影响。
  这个边界划得非常准。

问题有三个，按严重程度：

1. **解析失败是静默的**（[016](bug/016-annotation-declarations-fail-silently.md)，P0）。
   `get_type_hints` 抛异常时框架记一条 WARNING 就放行，单元少了它声明的协作者，
   `start()` 照样报成功，错误推迟到第一次访问属性时的 `AttributeError`。
   触发条件很日常：类定义在函数作用域里（测试里就地造假配置——必然触发）、
   或类上有任何一个 `if TYPE_CHECKING:` 导入的注解（那会把**同一个类上的所有**
   声明一起连坐掉，包括那行完全合法的 `log: logging.Logger`）。
   这条把「声明即注入」的确定性打掉了一半。

2. **升级时它会跟 `deps` 打架**（[015](bug/015-config-as-a-unit-collides-with-itself.md)）。
   0.9.2 的标准写法是 `@cocoa class AppConfig(BaseSettings)` + `deps=[AppConfig]` +
   一行给 mypy 看的 `app_config: AppConfig`。0.9.3 把最后那行变成了第二次声明，
   于是每一个声明了配置的单元都撞 `InjectionError`。场景一 6 处、场景二 8 处，
   必须一次改完才能启动，而报错信息没说该删哪一个。

3. **配好的配置取不回来**（[017](bug/017-injected-config-is-not-reachable-from-the-runtime.md)）。
   `canary[AppConfig]` 抛 `KeyError`，只能穿过某个恰好声明了它的单元去拿。
   生产入口为了决定往 `overrides` 里放什么，还得自己先 `AppConfig()` 一份，
   于是一个进程里有两份配置对象。

一句话：**注解声明这个方向是对的，建议把它走完**——
让类级注解也能声明普通依赖（见 [021](bug/021-substitution-and-injection-by-class-name-pull-apart.md)），
这样 `deps=[...]` 与注解不再是两条会打架的通道，注入名也不必等于类名。

---

## 其余修复的验证结果

逐条对照发布说明。✅ = 已验证并加了回归测试。

| 发布说明里的条目 | 结果 |
|---|---|
| 启动失败按台账逆序回滚（含失败单元自身），原异常原样抛出，回滚失败作为 note | ✅ 完全正确，包括 note |
| 一个 `@on_stop` 抛异常不再中断整轮关停，合并成 `ExceptionGroup` | ✅ 顺序、内容、`__notes__` 出处都对 |
| 失败之后 `stop()` 可调、幂等 | ✅ 且台账清空，回收只做一次 |
| lifespan 启动失败不再让进程永久挂起 | ⚠️ **对 uvicorn 成立，对 `TestClient` 变成了另一种挂起**（[019](bug/019-lifespan-startup-failure-hangs-the-test-client.md)） |
| pydantic 校验器抛 `ValueError` 时 422 不再崩成 500，`ctx` 约束值保留 | ✅ |
| handler 可返回 `Response`（SSE / 文件 / 自定义状态码 / `BackgroundTask`） | ✅ 四种全部验证 |
| 非标量参数走 body（`dict` / `list[Model]`） | ✅ |
| 单个类型生成不出 schema 时退化成"未约束"并记 WARNING | ✅ 其余端点的 schema 不受影响 |
| `{name:path}` 转换器不再泄漏进 OpenAPI | ✅ |
| `@on_request_error`：`__mro__` 查找、基类兜族、三条内置可覆盖、重复登记报错 | ✅ 五条全部验证 |
| `overrides=`：替身不必是 `@cocoa`、生命周期钩子照常、被替换类型不展开依赖、写错抛 `OverrideError` | ✅ 四条全部验证；**但带 `deps` 的替身抛裸 `KeyError`**（[018](bug/018-a-substitute-with-deps-fails-with-a-bare-keyerror.md)） |
| 配置：整图共享、可 `overrides`、pydantic-settings 优先级 | ✅ |
| 日志：只决定名字，不装 handler / 不设 format / 不碰 root | ✅ |
| 装配摘要（`canary.runtime` DEBUG） | ✅ 启动顺序 / 依赖 / 替身 / 路由 / 异常映射都在，排查路由缺失确实好用（**但只在启动成功时打印，见下**） |
| 500 响应体从 `text/plain` 变成 `application/json` | ✅（注意需要 `raise_server_exceptions=False` 才看得到 body） |
| 多根编排没有 after-all 位置 | ✅ 摘要里那条 note 写得很好；我们两个场景都保持单根 |
| `#007` 撞名不再"后写的赢" | ✅ 现在抛 `InjectionError` |

### 装配摘要的一条小建议

摘要打在 `start()` 的**末尾**，也就是只有启动成功才看得到：

```python
self._state = LifecycleState.STARTED
if _log.isEnabledFor(logging.DEBUG):
    _log.debug("%s", self._assembly_summary())
```

而最需要它的时刻恰恰是**启动失败**的时刻——"这个单元为什么先启动"、
"这条依赖是从哪来的"、"替身到底装上没有"，都是排查启动失败的问题。
建议在 `except` 分支里也打一次（把已经算出来的顺序和替身打出来，
再标出失败停在第几个），或者把摘要移到 `_order` 算完之后、
在 `init()` 末尾就打印结构部分，`start()` 末尾只补路由与异常映射。

另外一处顺序上的小别扭：摘要在应用自己的 `@on_start` 日志**之后**才出现
（因为它在整个 `start()` 之后），所以真实日志里读起来是"应用说自己起来了，
然后框架才说自己装了什么"。不影响使用，但如果摘要移到 `init()` 就顺了。

## 仍然缺失的（沿用旧编号）

- [#010](https://github.com/HotcocoaCanary/Canary-Framework) **后台任务 / 调度**：
  web 侧现在有了挂在响应上的 `BackgroundTask`（Starlette 的），
  但纯 core 的守护进程形态依然什么都没有。场景二仍然自带
  `SupervisedTasks` + `Scheduler` 两个单元约 200 行。
- **#009 请求作用域 / 事务边界**：场景一仍然是显式
  `async with self.database.begin()`，服务边界即事务边界。这个绕行我们其实不讨厌，
  但它仍然是「官方没给姿势」的状态。
- **#013 after-all 钩子**：0.9.3 把「多根没有 after-all」说清楚了（很好），
  但没补钩子。单根方案可用，我们继续用。

## 怎么复现这份报告

```bash
# 框架侧
cd Canary-Framework && git checkout release/0.9.3

# 本仓库已经把依赖指向本地工作副本（pyproject.toml 的 [tool.uv.sources]）
cd Canary-Agent
uv run pytest                       # 142 passed

# 三个独立的测量脚本
uv run pytest apps/library/tests/test_framework_boundaries.py -q     # web 面 26 条
uv run pytest apps/telemetry/tests/test_framework_boundaries.py -q   # 生命周期面 14 条
```
