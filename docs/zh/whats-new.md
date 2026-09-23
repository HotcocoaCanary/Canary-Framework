# 1.1 新特性

1.1 把引擎重建在显式的依赖图上。`init()`、`start()`、`stop()` 与 `async with` 的用法不变；
有两处变化会影响直接驱动引擎的代码，放在最前面。其余都是不需要改代码就能得到的行为。

从 1.0 升级？看前两节。从 0.9.x 升级？先看[从 0.9.x 升级](upgrading-from-0.9.md)，中间那个
版本的变化见 [1.0 新特性](whats-new-1.0.md)。

## 破坏性变更：引擎函数改名

`Canary` 的方法只是两个函数的薄包装，自定义阶段直接调用它们。现在它们按做的事情命名：

| 1.0 | 1.1 |
|---|---|
| `advance(unit, phase)` | `enter(unit, phase)` |
| `unwind(scope_of(unit), rollback, undoing=migrate)` | `leave(unit, migrate)` |
| — | `Phase("migrate", after=init, leave=rollback)` |

`leave()` 与 `stop()` 规则相同——先本单元，再依赖——离开钩子失败时抛 `ExceptionGroup`，而
`unwind()` 是返回列表。阶段现在用 `leave=` 声明离开它时运行的阶段；`start` 的是 `stop`。

```python
rollback = Phase("rollback")
migrate = Phase("migrate", after=init, leave=rollback)

await enter(unit, migrate)      # 运行 @migrate，依赖在前
await leave(unit, migrate)      # 运行 @rollback，本单元在前
```

## 破坏性变更：对仍被使用的单元调用 `stop()` 不做任何事

`stop()` 是单元的动作：停止被调用的那个单元，再以同样的方式尝试它的每个依赖。仍被使用的
单元——有依赖者正在启动、运行或停止——被跳过，不报错。1.0 里对*任何*单元调用 `stop()` 都
会回收整张图。

```python
async with service:
    await service.database.stop()   # 1.0：整张图停止。1.1：什么都不发生——service 还在用它。
```

要停止一切，停止根单元：`await service.stop()`。`async with` 做的正是这件事。

## 失败的 `start()` 自行清理

`@start` 抛出的单元立即运行自己的 `@stop`；依赖它的单元不启动，并释放它们正在等待的依赖。
`start()` 在它启动的一切都释放之后才抛出：

```
C.start → A.start → B.start ✗ → B.stop → A.stop → C.stop → start() 抛出 B 的异常
```

重试就是再调用一次 `start()`，中间不需要 `stop()`。与失败单元同时启动的单元不会被取消：
它们执行完毕，若不再被其他单元使用则随即释放。

## 环在任何钩子运行之前被发现

依赖图在单元第一次进入时构建，因此环、或尚未进入前驱阶段的单元，在任何钩子运行之前就被
报告。1.0 里无关分支上的钩子可能已经运行。

## 共享的依赖在最后一个使用者停止后才停止

```python
await root.left.start()
await root.right.start()    # 二者都依赖 Shared
await root.left.stop()      # left 停止；Shared 继续运行——right 还需要它
await root.right.stop()     # right，然后 Shared
```

## 1.1 还有

- Python 3.15 进入 CI 测试矩阵与 classifier。
- `Scope.key_of(unit)`、`Scope.entered(phase)`，以及用于观察依赖图和单元状态的
  `Scope.graph` / `Scope.dependents` / `Scope.tracks`。
- 随机化生命周期测试发现的三处引擎缺陷已修复，见
  [变更日志](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md)。
- [为什么选 Canary](why-canary.md)：适合与不适合的场景，以及与 dishka、dependency-injector、
  injector、FastAPI `Depends` 的实测对比。
