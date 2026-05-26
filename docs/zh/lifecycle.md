# 生命周期

三阶段钩子，全部可选。钩子名由 `LifecycleHook` 枚举定义，必须使用 `@on_init` / `@on_start` / `@on_end` 显式装饰。

```
Canary.init()  → on_init() → ...     （拓扑序）
Canary.start() → on_start() → ...     （拓扑序）
Canary.stop()  ← on_end() ← ...       （逆序）
```

## `on_init()`

此时依赖已注入、配置已作为属性加载。**`@on_init` 不再接收 `ctx` 参数** —— 所有依赖和配置直接通过 `self` 访问：

```python
@service(name="db", config=AppConfig)
class DBService:
    app_config: AppConfig

    @on_init
    def init(self) -> None:
        self.pool = create_pool(self.app_config.db_url)
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

# LifecycleHook.INIT   == "on_init"
# LifecycleHook.START  == "on_start"
# LifecycleHook.END    == "on_end"
```

## 异常处理

如果钩子方法抛出异常，框架会包装为 `LifecycleHookError`：

```python
from canary_framework import LifecycleHookError

try:
    await app.init()
except LifecycleHookError as e:
    print(f"钩子失败: {e}")
```
