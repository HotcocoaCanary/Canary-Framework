# API 参考

以下均从 `canary_framework` 导出，除非另有说明。

## `cocoa`

```python
def cocoa(cls=None, *, deps: list[type] | None = None)
```

把 `cls` 标记为 cocoa —— 最小单元。`deps` 是有序的依赖类型列表。可直接使用，也可作为
装饰器工厂：

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...
```

单元一律由框架**无参构造**：`__init__` 不能有必填参数，否则 `Canary(...)` 抛 `ConstructionError`。

## `on_init` / `on_start` / `on_stop`

```python
def on_init(fn) -> fn
def on_start(fn) -> fn
def on_stop(fn) -> fn
```

把方法注册为生命周期钩子。每个都接受同步或异步函数；同一阶段可有任意多个钩子，混入的
先于本类执行。

## `Canary`

```python
class Canary(*roots: type, start_concurrency: int | None = None)
```

编排器。构造即装配：建图（每个类型无参构造一次）、拓扑排序、注入依赖，全部同步完成；
装配类错误（`ConstructionError` / `InjectionError` / `CircularDependencyError`、非 cocoa 的
`TypeError`）在这一行抛出。

`start_concurrency`：`None`（默认）严格顺序；给一个正整数则让互不依赖的单元同时启动，同时
最多这么多个。见 [生命周期 · 并发启动](lifecycle.md#并发启动)。

### 属性

| 属性 | 类型 | 含义 |
|---|---|---|
| `state` | `LifecycleState` | 当前生命周期状态 |
| `order` | `tuple[type, ...]` | 拓扑启动顺序（依赖在前） |
| `instances` | `tuple[object, ...]` | 按拓扑序排列的实例 |
| `roots` | `tuple[type, ...]` | 构造时传入的根 |

### `__getitem__`

```python
def __getitem__(self, cls: type[T]) -> T
```

返回图中 `cls` 的共享单例；若不存在则抛出 `KeyError`。

### `init`

```python
async def init(self) -> None
```

`READY → INITIALIZED`。跑全部 `@on_init` —— 各就各位。依赖已在构造期注入，这里让每个单元
做"只需要依赖、不碰外部资源"的准备。失败置 `FAILED` 并抛出；台账为空，无需回收。

它是一道栅栏：全部 `@on_init` 完成之后，才允许任何 `@on_start`。栅栏就是本方法的返回。

### `start`

```python
async def start(self) -> None
```

`INITIALIZED → STARTED`。跑全部 `@on_start` —— 开工。进入 `@on_start` 的单元立刻记账。
在 `READY` 态调用（忘了 `init()`）会抛 `LifecycleError: call init() before start()`。

任一环节失败时，**进入过 `@on_start`** 的单元（含失败的那个）按逆序回收，然后原样抛出最初
的异常，回收过程中的异常作为 note 附在其上。

### `stop`

```python
async def stop(self) -> None
```

逆拓扑序执行 `@on_stop`。**唯一的回收路径**：从 `STARTED` 可调，从 `FAILED` 也可调，
重复调用是幂等的，没启动过时空转。单个 `@on_stop` 抛出不会中断回收 —— 异常收集完毕后
合并成一个 `ExceptionGroup` 抛出。

### `lifespan`

```python
@asynccontextmanager
def lifespan(self, _host: object = None) -> AsyncContextManager[None]
```

交给宿主的入口：进入时 `start()`，退出时 `stop()`，**交出 `None`**。

`_host` 收下宿主传进来的自己（ASGI 的 `lifespan(app)`、MCP 的 `lifespan(server)`），又给了
默认值，所以没有宿主时也能直接 `async with canary.lifespan():`。

```python
app = FastAPI(lifespan=canary.lifespan)
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
server = MCPServer("demo", lifespan=canary.lifespan)
```

交出 `None` 是必须的：ASGI 的 lifespan 协议把交出来的值当作要合并进 `scope["state"]` 的
映射。

### `__aenter__` / `__aexit__`

异步上下文管理器协议，封装 `start()` / `stop()`，**交出容器自己** —— 它服务的是
你自己的代码：

```python
async with Canary(Root) as canary:
    canary[SomeUnit].do_something()
```

## 枚举

### `LifecycleState`

`READY`、`INITIALIZING`、`INITIALIZED`、`STARTING`、`STARTED`、`STOPPING`、`STOPPED`、
`FAILED`。三个动作各有一个进行中状态与一个完成态；起点是 `READY`：装配在 `Canary(...)`
里已经做完。

### `State`

（`canary_framework.common.type`）所有状态枚举的基类；`issubclass` 校验的挂载点。

## 异常

| 异常 | 基类 | 含义 |
|---|---|---|
| `CanaryError` | `Exception` | 所有框架与扩展错误的根基类 |
| `CircularDependencyError` | `CanaryError` | 依赖成环；`.cycle` 是环上的类型名 |
| `ConstructionError` | `CanaryError` | 单元需要构造参数，框架无参构造不出来 |
| `InjectionError` | `CanaryError` | 两个依赖的 snake_case 撞名；`.attribute` / `.claimants` |
| `LifecycleError` | `CanaryError` | 非法生命周期迁移 |

所有框架错误都继承 `CanaryError`，因此 `except CanaryError` 可一网打尽。将来的扩展也应
继承它。

## 环境变量

| 变量 | 作用 |
|---|---|
| `CANARY_LOG_LEVEL` | `canary` logger 树的级别。设成 `DEBUG` 会打印装配摘要。 |
| `CANARY_SLOW_CALLBACK_SECONDS` | 事件循环延迟探针的阈值（秒）。开发期工具，默认关闭。 |

## 自省（`canary_framework.core.decorator.introspect`）

| 函数 | 作用 |
|---|---|
| `is_cocoa(cls)` | `cls` 是否被 `@cocoa` 标记 |
| `deps_of(cls)` | 声明的依赖（元组） |
| `init_hooks(instance)` / `start_hooks(instance)` / `stop_hooks(instance)` | 某阶段的钩子，基类优先 |
| `to_snake(name)` | （`core.infra.naming`）`UserService` → `user_service` |

## 图算法（`canary_framework.runtime.graph`）

| 函数 | 作用 |
|---|---|
| `build_graph(roots)` | 实例化每个根及其传递依赖，每类型一次，全部无参构造 |
| `topological_sort(graph)` | 卡恩算法；成环抛 `CircularDependencyError` |
