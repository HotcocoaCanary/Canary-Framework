# 服务

## 最小写法

```python
from canary_framework import service, on_start, Canary

@service(name="HelloService")
class HelloService:
    @on_start
    def start(self) -> None:
        print("started")
```

- `name`：全局唯一，必填
- 其他全可选

## 完整写法

```python
from canary_framework import service, on_init, on_end, Context

@service(
    name="UserService",         # 必填：全局唯一名称
    config=UserConfig,          # 可选：@config 装饰的配置类
    deps=[DBService],           # 可选：依赖列表，自动注入为 self.db_service
)
class UserService:
    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.config_as(UserConfig)  # 类型安全的配置访问
        self.db_service.query()          # 使用已注入的依赖

    @on_start
    async def start(self) -> None:
        await self.pool.connect()

    @on_end
    def end(self) -> None:
        self.pool.close()
```

## 生命周期钩子

钩子必须使用装饰器显式标记，框架不会按方法名自动识别：

```python
from canary_framework.core.decorators.lifecycle import LifecycleHook

# LifecycleHook.INIT   → @on_init    (拓扑序，接收 Context)
# LifecycleHook.START  → @on_start   (拓扑序，无参数)
# LifecycleHook.END    → @on_end      (逆序，无参数)
```

钩子方法可以是同步 (`def`) 或异步 (`async def`)，框架自动适配。
