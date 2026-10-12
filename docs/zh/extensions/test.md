# 测试

`canary_framework.test` 是两个测试辅助。它只依赖核心，不需要额外安装，也不绑定某个测试
框架。

```python
from canary_framework.test import running, unit
```

!!! note "暂行 API"
    扩展包在稳定之前可能在次版本中调整，见[版本与兼容性](../versioning.md#extensions)。

## `running`：带替身启动一张图

```python
async def test_alerts_fire_after_the_window() -> None:
    clock = ManualClock()
    async with running(TelemetryDaemon, {Clock: clock}) as daemon:
        clock.advance(30)
        ...
```

它构造一个新的根单元，把替身登记进作用域，启动整张图，退出时回收。每次调用都是一张新的图，
测试之间不共享任何实例。

替身经 [`Scope.provide`](../patterns.md) 登记，所以：

- 被替换的单元**不会被构造**，它的依赖也不会因此启动；
- 替身按自身的类型参与生命周期：运行自己的钩子，进入自己声明的依赖；
- 替身必须是被替换类型的实例，否则在任何单元启动之前抛出 `TypeError`。

## `unit`：按类型取回单元

```python
async with running(TelemetryDaemon) as daemon:
    store = unit(daemon, MetricStore)
```

日常代码应当从声明依赖的单元上读（`daemon.collector.store`）。测试常常要够到一个自己没有
声明过依赖的单元，这时用 `unit`。第一个参数可以是图上的任意单元。

它做的只是"从一张图上按类型取回单元"，所以不限于测试：在别的 Web 框架的接口里取单元时用的
也是它，见 [Web 服务器](server.md)。

图在第一次进入生命周期时才建立；在那之前取一个尚不存在的单元会抛出 `LookupError`。
