# 模块 (Modules)

在 Canary 框架中，模块（Module）负责对服务进行逻辑上的组织和聚合。它们自身也可以作为服务的消费者。

## 定义模块

使用 `@module()` 装饰器并将属于这个模块的服务传递给 `services` 参数：

```python
from canary_framework import module
from .database import Database
from .users import UserRepository

@module(services=[Database, UserRepository])
class UserModule:
    # 模块也可以拥有依赖和生命周期，就像普通服务一样
    repo: UserRepository

    async def init(self):
        print("User Module initialized.")
```

## 嵌套与架构

在大型应用中，你可以将多个子模块挂载到一个根模块上：

```python
from canary_framework import module
from .auth_module import AuthModule
from .user_module import UserModule

@module(services=[AuthModule, UserModule])
class AppModule:
    pass
```

然后，在启动时，你只需要将 `AppModule` 喂给 `Canary` 容器即可：

```python
from canary_framework.canary import Canary
from myapp.app_module import AppModule

app = Canary(AppModule())
```
容器会自动递归扫描所有的服务，并进行统一的拓扑排序和依赖注入。
