# Configuration

Canary Framework provides an extremely simple configuration system based on the Pydantic base class `CanaryConfig`.

## Defining a Configuration Class

Use the `@config()` decorator and inherit from `CanaryConfig`:

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    # You can define any Pydantic-supported fields
    db_url: str = "sqlite:///:memory:"
    api_key: str | None = None
```

## Mounting the Config in the Root Module

The configuration must be mounted in your root module (`@module`). The container will parse it automatically during startup:

```python
from canary_framework import module
from .config import AppConfig

@module(config_cls=AppConfig, services=[...])
class AppModule:
    pass
```

## Injecting and Using in Services

Following the same "Pure Type Hint DI" philosophy, simply annotate the configuration class type in your service, and the framework will naturally inject the globally unique configuration object:

```python
from canary_framework import service
from .config import AppConfig

@service()
class Database:
    cfg: AppConfig  # The framework auto-injects the config instance!

    async def startup(self):
        print(f"Connecting to {self.cfg.db_url}")
```
