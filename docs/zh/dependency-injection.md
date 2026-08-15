# 依赖注入

cocoa 通过 `@cocoa(deps=[...])` 声明依赖。无需额外 DSL，也无需 `__init__` 装配 —— 依赖图
就写在装饰器里。

## 契约

```python
@cocoa(deps=[Database, Cache])
class UserService: ...
```

`deps=[...]` 是一个有序的 cocoa 类型列表。在 `start()` 阶段，运行时把每个依赖注入到实例上，
属性名由类名转 snake_case 得到：

| 依赖类型 | 注入属性 |
|---|---|
| `Config` | `self.config` |
| `Database` | `self.database` |
| `UserService` | `self.user_service` |

```python
@cocoa(deps=[Database])
class UserService:
    @on_start
    def warm_up(self) -> None:
        self.database.ping()  # 在 @on_start 执行前已注入
```

因为注入发生在 `start()` 而非 `__init__`，构造函数保持空、单元构建廉价。不要在 `__init__`
里读注入属性；请用 `@on_init` 或 `@on_start`。

## 解析

`init()` 通过递归遍历每个根的 `deps=[...]` 建图，并把每个类型实例化一次。未被 `@cocoa`
标记的类型会抛出 `TypeError`。

依赖按具体类对象解析 —— 没有字符串、没有前向引用：

```python
@cocoa(deps=[Database])
class UserService: ...
```

## 共享

每个类型在**单张图内只实例化一次**。当多个单元依赖同一类型时，它们共享同一个实例：

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...


@cocoa(deps=[Config])
class Cache: ...


@cocoa(deps=[Database, Cache])
class Root: ...


app = Canary(Root)
await app.start()
assert app[Database].config is app[Cache].config  # 同一个 Config
```

共享作用域限于单个 `Canary`。两个独立的 `Canary` 实例会构建两张独立的图。

## 成环

成环会在 `init()` 阶段被拒绝。拓扑排序检测到环时抛出 `CircularDependencyError`，并通过
`.cycle` 暴露环上的类型：

```python
@cocoa(deps=[B])
class A: ...


@cocoa(deps=[A])
class B: ...


app = Canary(A)
await app.init()  # CircularDependencyError: circular dependency detected: A -> B -> A
```

## 多根图

给 `Canary` 传入多个根会合并它们的图。根之间共享的依赖仍只实例化一次：

```python
app = Canary(UserService, ReportService)
await app.start()
assert app[UserService].database is app[ReportService].database
```

## 命名边界情况

注入属性名由依赖的类名转 snake_case 而来。缩写也能正确处理（`APIService` →
`api_service`、`HTTPServer` → `http_server`）。若两个依赖会撞名，请重命名其中一个类 ——
注入属性由类型派生，而非列表顺序。
