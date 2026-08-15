# 生命周期

Canary 的生命周期建立在 Python 原生的对象与上下文管理协议之上。

## 两个用户 Hook

| 用户声明 | Python 协议 | 含义 |
|---|---|---|
| `__init__` | 对象构造 | 构造实例并注入依赖 |
| `@start` | `__aenter__` | 进入运行状态 |
| `@stop` | `__aexit__` | 离开运行状态 |

`@start`、`@stop` 两者可选。框架将 `@start` 映射到 `__aenter__`、`@stop` 映射到 `__aexit__`，因此 Canary 是一个异步上下文管理器。

## 状态机

每个 Canary 实例都跟踪其状态：

```
NEW ──▶ INITIALIZED ──▶ STARTING ──▶ RUNNING ──▶ STOPPING ──▶ STOPPED
                            │                     │
                            └───────▶ FAILED ◀───────┘
```

状态机保证生命周期操作按合法顺序执行。例如，已处于 `RUNNING` 的 Canary 不能再次启动：

```python
await database.__aenter__()
await database.__aenter__()  # LifecycleError: must be initialized before entering
```

## Flock 下的 Hook 顺序

`Flock` 按拓扑顺序驱动依赖图。对于 `APIService → UserService → Database`：

- **构造**（依赖优先）：`Database.__init__` → `UserService.__init__` → `APIService.__init__`。
- **启动**（依赖优先）：`Database.__aenter__` → `UserService.__aenter__` → `APIService.__aenter__`。
- **关闭**（逆序）：`APIService.__aexit__` → `UserService.__aexit__` → `Database.__aexit__`。

任何 Canary 在其所有依赖运行之前不会启动；任何 Canary 在其依赖停止之前就会停止。

## 启动回滚

若某 Canary 启动失败，`Flock` 按逆序停止所有已运行的 Canary，并抛出 `StartupError`：

```
Database started → UserService started → APIService starting（失败）
APIService FAILED → UserService.__aexit__ → Database.__aexit__
```

未达到 `RUNNING` 的 Canary 被标记为 `FAILED`；已达 `RUNNING` 的则被干净地停止。
