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

`INITIALIZED → STARTED`。按序执行 `@on_start`，随后合并所有 `@web_cocoa` 单元的路由为
统一服务入口。任一环节失败时，已进入 `@on_start` 的单元（含失败的那个）按逆序回收，然后
原样抛出最初的异常，回收过程中的异常作为 note 附在其上。

### `stop`

```python
async def stop(self) -> None
```

逆拓扑序执行 `@on_stop`。**唯一的回收路径**：从 `STARTED` 可调，从 `FAILED` 也可调，
重复调用是幂等的，没启动过时空转。单个 `@on_stop` 抛出不会中断回收 —— 异常收集完毕后
合并成一个 `ExceptionGroup` 抛出。

### `__call__` — ASGI

```python
async def __call__(self, scope, receive, send) -> None
```

服务 ASGI：`lifespan` 驱动生命周期；其余 scope 委托给合并出的服务入口。没有 lifespan 时
第一个请求会顺手启动应用，并发的首批请求会排队等同一次启动。

### `__aenter__` / `__aexit__`

异步上下文管理器协议，封装 `init()` + `start()` / `stop()`。

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
| `DeclarationError` | `CanaryError` | 声明打在了读不到它的地方（如 `@get` 写在普通 `@cocoa` 上） |
| `InjectionError` | `CanaryError` | 两个依赖的 snake_case 撞名；`.attribute` / `.claimants` |
| `LifecycleError` | `CanaryError` | 非法生命周期迁移 |

所有框架与扩展错误都继承 `CanaryError`，因此 `except CanaryError` 可一网打尽。

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
| `marked_members(instance, marker)` | 带该标记的方法，返回 `(载荷, 绑定方法)`，基类优先 |
| `init_hooks(instance)` / `start_hooks(instance)` / `stop_hooks(instance)` | 某阶段的钩子 |
| `to_snake(name)` | （`core.infra.naming`）`UserService` → `user_service` |

## 图算法（`canary_framework.runtime.graph`）

| 函数 | 作用 |
|---|---|
| `build_graph(roots)` | 实例化每个根及其传递依赖，每类型一次，全部无参构造 |
| `topological_sort(graph)` | 卡恩算法；成环抛 `CircularDependencyError` |

## Web 扩展（`canary_framework.web`）

| 名称 | 作用 |
|---|---|
| `@web_cocoa(deps=[...], prefix="", tags=(), title="Canary API", version="0.1.0")` | 把类同时标记为 `@cocoa` 与 HTTP 路由持有者；`prefix` 是**绝对**前缀 |
| `@get` / `@post` / `@put` / `@patch` / `@delete` `(path, *, status_code=200, tags=(), summary=None, deprecated=False)` | 把方法标记为路由处理器（必须 `async def`） |
| `@route(method, path, ...)` | 上面五个的通用形式 |
| `Header(*, description=None, alias=None)` | 请求头参数，写在 `Annotated` 里 |
| `Cookie(*, description=None, alias=None)` | cookie 参数，写在 `Annotated` 里 |
| `HTTPError(status_code, detail=None, headers=None)` | 自带 HTTP 语义的错误 |
| `WebError` | web 扩展错误的根基类（继承 `CanaryError`） |
| `RouteRegistrationError` | 路由无法注册：重复的 method + path、handler 不是 `async def`、两个请求体形参…… |
| `RequestValidationError` | 请求绑不上签名，映射为 422 |

用法见 [Web 应用](web.md)。
