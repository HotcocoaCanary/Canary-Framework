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

## `on_init` / `on_start` / `on_stop`

```python
def on_init(fn) -> fn
def on_start(fn) -> fn
def on_stop(fn) -> fn
```

把方法注册为生命周期钩子。每个都接受同步或异步函数；同一阶段可有任意多个钩子。

## `Canary`

```python
class Canary(*roots: type)
```

编排器。若某个根未被 `@cocoa` 标记，抛出 `TypeError`。

### `state` — 属性

```python
@property
def state(self) -> LifecycleState
```

当前生命周期状态。

### `order` — 属性

```python
@property
def order(self) -> tuple[type, ...]
```

拓扑启动顺序中的单元类型（依赖在前）。

### `instances` — 属性

```python
@property
def instances(self) -> tuple[object, ...]
```

按拓扑序排列的实例。

### `__getitem__`

```python
def __getitem__(self, cls: type[T]) -> T
```

返回图中 `cls` 的共享单例；若不存在则抛出 `KeyError`。

### `init`

```python
async def init(self) -> None
```

建图、拓扑排序、按序执行 `@on_init`。`NEW → INITIALIZED`。

### `start`

```python
async def start(self) -> None
```

注入依赖、按序执行 `@on_start`、随后收集服务入口。`INITIALIZED → STARTED`。

### `stop`

```python
async def stop(self) -> None
```

逆拓扑序执行 `@on_stop`。`STARTED → STOPPED`。

### `__call__` — ASGI

```python
async def __call__(self, scope, receive, send) -> None
```

服务 ASGI：`lifespan` 驱动生命周期；其余 scope 委托给单元在 `start()` 阶段暴露的服务入口。

### `__aenter__` / `__aexit__`

异步上下文管理器协议，封装 `init()` + `start()` / `stop()`。

## 枚举

### `LifecycleState`

`NEW`、`INITIALIZING`、`INITIALIZED`、`STARTING`、`STARTED`、`STOPPING`、`STOPPED`、
`FAILED`。

### `State`

所有状态枚举的基类；`issubclass` 校验的挂载点，自身不直接使用。

## 异常

| 异常 | 基类 | 含义 |
|---|---|---|
| `CanaryError` | `Exception` | 所有框架错误的根基类 |
| `CircularDependencyError` | `CanaryError` | 依赖成环；暴露 `.cycle`（类型名列表） |
| `LifecycleError` | `CanaryError` | 非法生命周期迁移 |

所有框架与扩展错误都继承 `CanaryError`，因此 `except CanaryError` 可一网打尽。

## 自省（`canary_framework.core`）

| 函数 | 作用 |
|---|---|
| `is_cocoa(cls)` | `cls` 是否被 `@cocoa` 标记 |
| `deps_of(cls)` | 声明的依赖 |
| `hooks_of(instance, marker)` | `instance` 上被标记的方法，基类优先 |
| `init_hooks(instance)` / `start_hooks(instance)` / `stop_hooks(instance)` | 某阶段的钩子 |
| `to_snake(name)` | `UserService` → `user_service` |

## 图算法（`canary_framework.runtime`）

| 函数 | 作用 |
|---|---|
| `build_graph(roots)` | 实例化每个根及其传递依赖，每类型一次 |
| `topological_sort(graph)` | 卡恩算法；成环抛 `CircularDependencyError` |

## Web 扩展（`canary_framework.web`）

| 名称 | 作用 |
|---|---|
| `@web_cocoa(deps=[...], title=..., version=...)` | 把类同时标记为 `@cocoa` 与 HTTP 路由持有者 |
| `@get` / `@post` / `@put` / `@patch` / `@delete` / `@route(method, path)` | 把方法标记为路由处理器 |
| `Query` / `Path` / `Header` / `Cookie` / `Body` | 参数来源标记（作默认值或经 `Annotated`） |
| `WebError` | web 扩展错误的根基类 |
| `RouteRegistrationError` | method + path 重复 |
| `MissingParameterError` | 必填请求参数缺失（映射为 HTTP 422） |

用法见 [Web 应用](web.md)。
