# 依赖声明

## `dep()`

用 `dep()` 在类体里声明一条依赖：

```python
from canary_framework import Canary, dep


class UserService(Canary):
    database = dep(Database)
    cache = dep(Cache)
```

它是一个描述符，读取时从所在作用域取回共享实例。三条性质：

**属性名由你决定。** 注入名不来自被依赖的类名，因此可以为实现类起一个抽象的名字：

```python
class AlertDispatcher(Canary):
    sink = dep(LoggingAlertSink)     # self.sink，不是 self.logging_alert_sink
```

**类型是推断出来的。** `dep()` 的返回值标注为被依赖的类型，所以 `database` 的类型就是
`Database`，不必另写注解，类型检查器与 IDE 都能识别。

**声明不需要求值。** 描述符持有的是类对象本身而非名字，因此不受
`from __future__ import annotations`、`if TYPE_CHECKING` 或函数作用域的影响。

## 只能依赖单元

```python
class Plain: ...


class Broken(Canary):
    thing = dep(Plain)
```

```
DeclarationError: dep(<class 'Plain'>): not a Canary subclass
```

检查发生在类体求值的那一刻，错误指向写下 `dep(...)` 的那一行。类型检查器也会拒绝它，
因为 `dep()` 的类型参数以 `Canary` 为界。

## 依赖何时可用

依赖在 `@init` 之后可用，在 `__init__` 中不可用：

```python
class Broken(Canary):
    config = dep(Config)

    def __init__(self) -> None:
        print(self.config)      # LifecycleError
```

```
LifecycleError: Broken.config is unavailable before the lifecycle begins.
Dependencies exist from @init onward, not in __init__.
```

## 作用域：一个作用域就是一张图

一次运行共享的状态保存在 `Scope` 里。作用域由**第一个被驱动的单元**创建，它就是这张图
的根；图上其余实例都由框架构造并登记进同一个作用域。

**同一个作用域内，每个类型只有一个实例。** 菱形依赖只会得到一份共享实例：

```python
class Left(Canary):
    config = dep(Config)


class Right(Canary):
    config = dep(Config)


class Root(Canary):
    left = dep(Left)
    right = dep(Right)


root = Root()
await root.init()
assert root.left.config is root.right.config      # 同一个
```

**两个各自构造的根是两张互不相干的图。** 连共享依赖也是两份：

```python
a, b = Root(), Root()
await a.init()
await b.init()
assert a.left is not b.left
assert a.left.config is not b.left.config
```

需要观察作用域时用 `scope_of()`：

```python
from canary_framework import scope_of

scope = scope_of(root)
scope.instances          # 类型 -> 实例
scope.entered["start"]   # 类型 -> 进入 start 阶段的单元，按进入顺序
```

## 依赖成环

```python
class A(Canary): ...


class B(Canary):
    a = dep(A)


A.b = dep(B)
```

```
CircularDependencyError: circular dependency: A -> B -> A
```

异常携带的是推进时实际走过的那条路径。实践中环很难写出来：`dep(B)` 在类体求值时 `B`
必须已经存在，所以直接的相互依赖写不出来。
