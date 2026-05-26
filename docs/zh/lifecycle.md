# 生命周期

四阶段钩子 + app 阶段的分离，全部可选。钩子名由 `LifecycleHook` 枚举定义，必须使用 `@on_config` / `@on_init` / `@on_start` / `@on_end` 显式装饰。

```
app.config()  → wiring + on_config() → ...   （拓扑序）
app.init()    → on_init() → ...              （拓扑序）
app.start()   → on_start() → ...             （拓扑序）
app.stop()    ← on_end() ← ...               （逆序）
```

## `app.config()`

调用 `app.config(config=ConfigModel())` 触发 wiring 和 `@on_config` 钩子。Config 属性在此阶段可用：

```python
from pydantic import BaseModel

class AppConfig(BaseModel):
    db_url: str = "postgresql://"

app = Canary(RootModule)
await app.config(config=AppConfig())
```

## `on_config()`

在 wiring 之后、`on_init` 之前执行。此时 config 属性已通过字段名匹配注入为实例属性：

```python
from pydantic import BaseModel

class DBConfig(BaseModel):
    pool_size: int = 10

@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.pool_size)  # DBConfig 的字段直接可用
```

## `on_init()`

Config 属性已在 `on_config` 阶段就绪。**`@on_init` 不再接收 `ctx` 参数** —— 所有依赖和配置直接通过 `self` 访问：

```python
@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.db_url)

    @on_init
    def init(self) -> None:
        self.pool.validate()
```

## `on_start()`

```python
@on_start
async def start(self) -> None:
    await self.pool.connect()
```

## `on_end()`

```python
@on_end
def end(self) -> None:
    self.pool.close()
```

钩子可以是 `async def` —— 框架通过 `asyncio.iscoroutine` 自动检测并 `await`。

## LifecycleHook 枚举

```python
from canary_framework import LifecycleHook

# LifecycleHook.CONFIG == "on_config"
# LifecycleHook.INIT   == "on_init"
# LifecycleHook.START  == "on_start"
# LifecycleHook.END    == "on_end"
```

## 异常处理

如果钩子方法抛出异常，框架会包装为 `LifecycleHookError`：

```python
from canary_framework import LifecycleHookError

try:
    await app.config(config=AppConfig())
except LifecycleHookError as e:
    print(f"配置阶段失败: {e}")
```
