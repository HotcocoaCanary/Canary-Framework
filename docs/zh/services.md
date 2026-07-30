# 服务

Service 是受生命周期管理、支持依赖注入的领域对象。它不可作为 ASGI 调用，也不能直接被服务。

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class Repository(ServiceBase):
    async def on_init(self) -> None:
        self.cache: dict[int, str] = {}

    def get(self, item_id: int) -> str | None:
        return self.cache.get(item_id)
```

使用类级类型注解声明依赖。Service 只能依赖 Service；Router 只能依赖 Service；Module 负责组合而不是向上注入 Router/Module。

状态依次为 `CREATED`、`INITIALIZED`、`STARTED`、`STOPPED`；任一转换失败进入 `FAILED`。非法重复公开转换会被拒绝。初始化失败会尽力逆序清理，同时保留原始失败。

少量 HTTP 专属逻辑可以留在 Router；需要复用、独立测试或资源管理时提取为 Service。
