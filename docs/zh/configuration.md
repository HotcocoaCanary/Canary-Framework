# 配置

配置属于运行根或 Module 上下文，不是依赖注入 Service，也不能放进 children。

```python
from canary_framework import CanaryConfig, config, module
from canary_framework.core import ModuleBase

@config()
class AppConfig(CanaryConfig):
    openapi_title: str = "Inventory API"
    openapi_version: str = "1.0.0"

@module(children=(InventoryRouter,), config=AppConfig)
class App(ModuleBase):
    pass
```

最近的 Module 配置向后代传播，除非嵌套 Module 自己覆盖。独立 Router 可通过 `@router(config=AppConfig)` 持有配置。

运行根配置唯一决定 OpenAPI title、version、description、servers、安全方案与文档路径。可变设置使用 Pydantic `Field(default_factory=...)`。
