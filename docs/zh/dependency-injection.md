# 依赖注入

Canary 通过构造函数类型注解表达依赖关系，无需额外的 DSL —— 依赖图直接存在于类型定义中。

## 契约

一个 `__init__` 参数是依赖，当它：

- 具有**类注解**（或**字符串前向引用**），且
- **没有默认值**。

```python
@canary
class UserService:
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache
```

规则：

- 带默认值的参数永远不会被注入。
- 无注解的参数，或注解为非类类型的参数，必须带默认值 —— 否则在装饰阶段抛出 `RegistrationError`。
- `*args` 与 `**kwargs` 会被 `RegistrationError` 拒绝。

## 解析

框架读取 `inspect.signature` 与 `typing.get_type_hints` 来解析依赖。参数名在装饰阶段分类；具体类型在构图阶段解析，因此支持前向引用。

每个解析出的依赖都必须是已注册的 Canary。依赖普通 class 会抛出 `DependencyError`。

## 前向引用

由于依赖在注册之后才解析，字符串前向引用可用 —— 前提是 Canary 类型定义在**模块级别**：

```python
from __future__ import annotations


@canary
class Database:
    def __init__(self, config: "Config") -> None:  # 前向引用
        self.config = config


@canary
class Config:
    pass
```

前向引用相对于模块全局命名空间解析。定义在函数体内部的 Canary 无法可靠解析前向引用 —— 请改为模块级别定义。

## 循环依赖

循环依赖会被拒绝。依赖图在拓扑排序阶段检测到它并抛出 `CircularDependencyError`：

```python
@canary
class A:
    def __init__(self, b: "B") -> None:
        ...


@canary
class B:
    def __init__(self, a: A) -> None:
        ...


flock = A.run()
await flock.start()  # CircularDependencyError: Circular dependency detected: A -> B -> A
```

## 作用域

每个 Canary 类型在每个 `Flock` 图中**只实例化一次**。多个 Canary 依赖同一类型时共享同一实例：

```python
@canary
class Database:
    def __init__(self, config: Config) -> None:
        ...


@canary
class Cache:
    def __init__(self, config: Config) -> None:
        ...


@canary
class Root:
    def __init__(self, database: Database, cache: Cache) -> None:
        ...


flock = Root.run()
await flock.start()
assert flock[Database].config is flock[Cache].config
```
