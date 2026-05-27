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
from canary_framework import config, service, on_config, on_init, on_end

@config
class AppConfig:
    max_items: int = 100

@service(
    name="UserService",         # 必填：全局唯一名称
    deps=[DBService],           # 可选：依赖列表，自动注入为 self.db_service
)
class UserService:
    db_service: DBService

    @on_config
    def setup(self) -> None:
        self.max_items = self.config.max_items  # config 通过 self.config 访问

    @on_init
    def init(self) -> None:
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
from canary_framework import LifecycleHook

# LifecycleHook.CONFIG → @on_config  （wiring 后、on_init 前，config 属性可用）
# LifecycleHook.INIT   → @on_init    （拓扑序）
# LifecycleHook.START  → @on_start   （拓扑序，无参数）
# LifecycleHook.END    → @on_end     （逆序，无参数）
```

钩子方法可以是同步 (`def`) 或异步 (`async def`)，框架自动适配。

## Config 和 Deps 作为属性

依赖通过 DI 注入为实例属性。Config 通过 `self.config` 访问，在所有服务和模块中自动可用：

```python
from canary_framework import config

@config
class AppConfig:
    dsn: str = "sqlite://"

@service(name="db", deps=[CacheService])
class DBService:
    cache_service: CacheService

    @on_config
    def setup(self) -> None:
        self.pool = connect(self.config.dsn)
```


