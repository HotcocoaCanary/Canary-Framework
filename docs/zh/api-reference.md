# API 参考

## `canary`

```python
def canary(cls: type[T]) -> type[T]
```

声明 `cls` 为 Canary。返回一个携带相同命名空间的 `Canary` 子类。

若 `cls` 已是 Canary、使用了 `__slots__`、声明了非法构造函数，或为同一阶段声明了重复 Hook，则抛出 `RegistrationError`。

## `Canary`

所有 Canary 共享的基类。

### `run` —— classmethod

```python
@classmethod
def run(cls) -> Flock
```

返回编排该 Canary 传递依赖图的 `Flock`。

### `state` —— 属性

```python
@property
def state(self) -> LifecycleState
```

返回实例当前的生命周期状态。

### `__aenter__`

```python
async def __aenter__(self) -> Canary
```

执行 `@start` Hook 并进入 `RUNNING` 状态。若未处于 `INITIALIZED` 则抛出 `LifecycleError`。

### `__aexit__`

```python
async def __aexit__(self, exc_type, exc, tb) -> bool | None
```

执行 `@stop` Hook 并进入 `STOPPED` 状态。若未运行则空操作。

## `start`、`stop`

```python
def start(func: F) -> F
def stop(func: F) -> F
```

将方法标记为 Canary 的启动 / 停止 Hook。每个都可是同步或异步，且每个 Canary 每阶段最多一个。

## `Flock`

```python
class Flock:
    def __init__(self, root: type[Canary]) -> None
```

由 `Canary.run()` 返回的生命周期编排器。若 `root` 不是已注册 Canary，则抛出 `DependencyError`。

### `root` —— 属性

根 Canary 类型。

### `state` —— 属性

```python
@property
def state(self) -> FlockState
```

当前编排状态。

### `order` —— 属性

```python
@property
def order(self) -> tuple[type[Canary], ...]
```

按依赖优先的拓扑顺序排列的 Canary 类型。

### `instances` —— 属性

```python
@property
def instances(self) -> dict[type[Canary], Canary]
```

以 Canary 类型为键的已创建实例副本。

### `__getitem__`

```python
def __getitem__(self, canary_type: type[T]) -> T
```

返回图中 `canary_type` 的共享实例。若不存在则抛出 `KeyError`。

### `start`

```python
async def start(self) -> None
```

构建依赖图、构造并按拓扑顺序启动每个 Canary。失败时（回滚后）抛出 `StartupError`。

### `stop`

```python
async def stop(self) -> None
```

按逆拓扑顺序停止运行中的 Canary。若未运行则抛出 `LifecycleError`。

### `__aenter__` / `__aexit__`

包装 `start` / `stop` 的异步上下文管理协议。

## 枚举

### `LifecycleState`

每个 Canary 的状态：`NEW`、`INITIALIZED`、`STARTING`、`RUNNING`、`STOPPING`、`STOPPED`、`FAILED`。

### `FlockState`

每个 Flock 的状态：`NEW`、`STARTING`、`RUNNING`、`STOPPING`、`STOPPED`、`FAILED`。

## 异常

| 异常 | 基类 | 含义 |
|---|---|---|
| `CanaryError` | `Exception` | 所有框架异常的基类 |
| `RegistrationError` | `CanaryError` | 非法的 Canary 声明 |
| `DependencyError` | `CanaryError` | 依赖解析或装配失败 |
| `CircularDependencyError` | `DependencyError` | 依赖环；暴露 `.cycle` |
| `LifecycleError` | `CanaryError` | 非法的生命周期操作 |
| `StartupError` | `CanaryError` | 启动失败；暴露 `.canary_type` |
