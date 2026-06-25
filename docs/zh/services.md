# 服务 (Services)

服务（Service）是 Canary Framework 应用程序中最基本的构建块。任何包含了业务逻辑的普通 Python 类都可以被标记为服务。

## 定义服务

要定义一个服务，只需要给一个类加上 `@service()` 装饰器：

```python
from canary_framework import service

@service()
class Database:
    async def query(self, sql: str):
        return {"status": "success", "sql": sql}
```

框架会：
1. **自动注册**：将其注册为全局 DI 容器可解析的目标。
2. **零侵入**：不需要继承任何基类，你的类依然是一个纯净的 Python 类。

## 声明并注入依赖

你唯一需要做的就是使用类型注解 (Type Hints) 来告诉容器你的服务需要什么。

```python
from canary_framework import service

@service()
class UserRepository:
    db: Database  # 框架会自动将实例化的 Database 注入这里

    async def get_user(self, user_id: int):
        return await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
```

## 生命周期钩子

你的服务可以自由地定义 `init`, `startup`, `shutdown` 等异步钩子。请参考 [生命周期管理](lifecycle.md)。
