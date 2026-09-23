# 1.0 新特性

1.0 是第一个稳定版本。0.10 引入的 API 从此受[语义化版本](versioning.md)约束：2.0 之前不做
破坏性变更，任何移除都至少提前一个次版本弃用。

从 0.9.x 升级？先看[从 0.9.x 升级](upgrading-from-0.9.md)。 当前版本的变化见 [1.1 新特性](whats-new.md)。

## 在整张图上替换依赖

`Scope.provide()` 让一个实例在整张图上顶替某个依赖——这是使用测试替身的正式方式：

```python
service = UserService()
scope_of(service).provide(Database, FakeDatabase())

async with service:
    assert service.repository.database is service.database     # 都是替身
```

登记的单元运行自己的钩子，推进自己的类声明的依赖。

给依赖属性赋值现在会抛 `AttributeError` 并指向 `provide()`。在 0.10 中它只会静默改掉这一个
属性，图中其余单元与生命周期仍使用原来的实例。

## 再次启动

`stop()` 会撤销 `start`，因此同一张图可以再次启动。`@init` 不会重跑：

```python
async with service:     # init、start、stop
    ...
async with service:     # start、stop
    ...
```

在 0.10 中第二次 `start()` 不运行任何钩子就直接返回。

## 失败后重试

失败或被取消的推进不再留下记录，因此再次调用会重新运行。在 0.10 中之后的每次调用都会原样
抛出第一次的异常。与此相关，`init()` 失败之后调用 `start()` 现在会抛 `LifecycleError`，而不是
继续执行。

## 从 0.10 升级

| 0.10 | 1.0 |
|---|---|
| `service.database = FakeDatabase()` | 在生命周期开始之前 `scope_of(service).provide(Database, FakeDatabase())` |
| `for unit in scope.entered["start"]` | `for unit in scope.entered["start"].values()`——以类型为键 |
| 新建一个根单元来重启 | 在同一个根单元上再次调用 `start()` |
