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

单元一律由框架**无参构造**：`__init__` 不能有必填参数，否则 `init()` 抛
`ConstructionError`。

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
class Canary(*roots: type)
```

编排器。若某个根未被 `@cocoa` 标记，抛出 `TypeError`。构造本身不做任何事。

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

`NEW → INITIALIZED`。建图（每个类型无参构造一次）、校验、拓扑排序、**注入依赖**、按序
执行 `@on_init`。失败置 `FAILED` 并抛出，**不回滚**（此时还没有任何 `@on_start` 跑过）。

### `start`

```python
async def start(self) -> None
```

`INITIALIZED → STARTED`。按序执行 `@on_start`。任一环节失败时，已进入 `@on_start` 的单元
（含失败的那个）按逆序回收，然后原样抛出最初的异常，回收过程中的异常作为 note 附在其上。

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

交给宿主的入口：进入时 `init()` + `start()`，退出时 `stop()`，**交出 `None`**。

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

异步上下文管理器协议，封装 `init()` + `start()` / `stop()`，**交出容器自己** —— 它服务的是
你自己的代码：

```python
async with Canary(Root) as canary:
    canary[SomeUnit].do_something()
```

## 枚举

### `LifecycleState`

`NEW`、`INITIALIZING`、`INITIALIZED`、`STARTING`、`STARTED`、`STOPPING`、`STOPPED`、
`FAILED`。

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
