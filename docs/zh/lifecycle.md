# 生命周期

三阶段钩子，全部可选。钩子名由 `LifecycleHook` 枚举定义，必须使用 `@on_init` / `@on_start` / `@on_end` 显式装饰。

```
Canary.init()  → on_init(ctx) → ...   （拓扑序）
Canary.start() → on_start() → ...     （拓扑序）
Canary.stop()  ← on_end() ← ...       （逆序）
```

## `on_init(ctx)`

接收 Context，此时依赖已注入、配置已加载：

```python
@on_init
def init(self, ctx: Context) -> None:
    cfg = ctx.config_as(AppConfig)
    self.pool = create_pool(cfg.db_url)
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

钩子可以是 `async def`，框架通过 `asyncio.iscoroutine` 自动判断并 `await`。

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
    print(f"Hook failed: {e}")
```
