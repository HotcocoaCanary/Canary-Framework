# Configuration

Configuration is runtime-root or Module context, not a dependency-injected Service and never a child.

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

The nearest Module config propagates to descendants unless a nested Module owns an override. A standalone Router may own config through `@router(config=AppConfig)`.

The runtime root config exclusively defines OpenAPI title, version, description, servers, security schemes, and documentation endpoint paths. Use Pydantic `Field(default_factory=...)` for mutable settings.
