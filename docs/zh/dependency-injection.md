# 依赖注入 (Dependency Injection)

Canary 采用了极其优雅的 **基于类型注解 (Type Hint) 的无侵入依赖注入系统**。
你**不需要**使用复杂的依赖收集器、也不需要显式写 `@depends` 标记。引擎通过反射 Python 标准的类属性注解，全自动完成所有脏活。

## 如何声明依赖？

只需要在你的类变量中标注对应服务的类型即可：

```python
from canary_framework import service

@service()
class Database:
    pass

@service()
class Cache:
    pass

@service()
class UserRepository:
    db: Database    # 框架会自动在运行时将 Database 实例注入到 self.db 
    cache: Cache    # 框架会自动将 Cache 实例注入到 self.cache

    async def get_user(self, user_id):
        # 你可以直接使用依赖，它们绝对保证已经被初始化！
        cached = await self.cache.get(f"user:{user_id}")
        ...
```

**注意事项：**
- 注入发生在类的实例化阶段（`__init__` 之后，`init` 钩子之前）。
- 属性的名字完全由你决定（你可以写 `my_db: Database`，那它就会注入到 `self.my_db` 里）。
- 被注入的类型必须同样是被 `@service()` 或 `@module()` 装饰过的类。

## 防止循环依赖

Canary 内置了严格的有向无环图（DAG）验证机制。如果你写出了类似鸡生蛋、蛋生鸡的互相依赖：

```python
@service()
class A:
    b: 'B'

@service()
class B:
    a: 'A'
```

引擎会在容器启动的一瞬间直接抛出 `CircularDependencyError` 异常，而绝不会导致运行时陷入死锁。

## 初始化安全保障

借助图论中的拓扑排序算法，Canary 保证一个服务的依赖在其自身创建之前，**必定已经完成了创建和初始化**。你永远不会遇到依赖组件还是空指针或未初始化状态的问题。
