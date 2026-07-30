# 生命周期

每个节点共用一个显式状态机：

`CREATED → INITIALIZED → STARTED → STOPPED`；失败进入 `FAILED`。

```python
@service()
class Database(ServiceBase):
    async def on_init(self) -> None:
        self.pool: Pool | None = None

    async def on_startup(self) -> None:
        self.pool = await create_pool()

    async def on_shutdown(self) -> None:
        if self.pool is not None:
            await self.pool.close()
```

- `on_init`：不需要事件循环资源的确定性结构准备。
- `on_startup`：依赖事件循环的长生命周期资源。
- `on_shutdown`：优雅清理。

扩展点必须是 async。公开 `init`、`startup`、`shutdown` 会拒绝非法重复，不应覆盖。服务前必须 `await app.init()`；ASGI lifespan 只负责启动/关闭，未初始化根会被拒绝。

依赖先于消费者初始化/启动，并以反序关闭。失败时引擎执行私有、幂等的回滚且保持 `FAILED`；这些回滚方法不是公共 API。
