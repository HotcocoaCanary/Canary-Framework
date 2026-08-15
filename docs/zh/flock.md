# Flock

`Flock` 是 `Canary.run()` 返回的可选编排器。它接收一个根 Canary，并驱动其传递依赖图的完整生命周期：

1. 发现依赖，
2. 构建依赖图，
3. 进行拓扑排序，
4. 按拓扑顺序为每个 Canary 类型构造一个共享实例，
5. 按拓扑顺序执行 `__aenter__`，
6. 关闭或失败时按逆拓扑顺序执行 `__aexit__`。

`Flock` 本身不是业务服务 —— 它只编排生命周期。Canary 无需它也可运行。

## 构造

```python
from canary_framework import canary


@canary
class APIService: ...


flock = APIService.run()
```

根节点必须是已注册的 Canary，否则抛出 `DependencyError`。

## 启动与停止

```python
await flock.start()
...
await flock.stop()
```

- `start` 构建依赖图、初始化并按顺序启动每个 Canary。
- `stop` 按逆序停止运行中的 Canary。
- `Flock` 也支持异步上下文管理协议：

```python
async with APIService.run() as flock:
    ...
```

## 访问实例

使用 `__getitem__` 获取图中某个 Canary 类型的共享实例：

```python
users = flock[UserService]
assert users.database is flock[Database]
```

`instances` 属性返回以 Canary 类型为键的实例映射副本。`order` 属性返回拓扑顺序（依赖优先）。

## 编排状态

`flock.state` 遵循 `FlockState`：

```
NEW → STARTING → RUNNING → STOPPING → STOPPED
                        └──▶ FAILED
```

## 失败与回滚

若启动期间任一 Canary 失败，`Flock` 会回滚：按逆序停止所有已运行的 Canary，将进行中的 Canary 标记为 `FAILED`，把自身状态置为 `FAILED`，并抛出链接原始异常的 `StartupError`。
