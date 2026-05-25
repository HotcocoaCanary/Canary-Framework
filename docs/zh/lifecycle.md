# 生命周期

三阶段钩子，全部可选。

```
Canary.init()  → on_init(ctx) → ...   （拓扑序）
Canary.start() → on_start() → ...     （拓扑序）
Canary.stop()  ← on_end() ← ...       （逆序）
```

## `on_init(ctx)`

接收 Context，此时依赖已注入、配置已加载：

```python
@on_init
def init(self, ctx: Context):
    self.pool = create_pool(ctx.config.db_url)
```

## `on_start()`

```python
@on_start
async def start(self):
    await self.pool.connect()
```

## `on_end()`

```python
@on_end
def end(self):
    self.pool.close()
```

钩子可以是 `async def`，框架自动判断并 `await`。
