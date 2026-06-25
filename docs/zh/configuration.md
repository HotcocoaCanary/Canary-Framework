# 配置 (Configuration)

Canary Framework 提供了一个极其简单的配置系统，基于 Pydantic 的基类 `CanaryConfig`。

## 定义配置类

通过 `@config()` 装饰器并将类继承自 `CanaryConfig`：

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    # 你可以定义任何 Pydantic 支持的字段
    db_url: str = "sqlite:///:memory:"
    api_key: str | None = None
```

## 在根模块中挂载配置

必须将配置挂载在你的根模块（`@module`）中，容器在启动时会自动解析它：

```python
from canary_framework import module
from .config import AppConfig

@module(config_cls=AppConfig, services=[...])
class AppModule:
    pass
```

## 在服务中注入和使用

同样是基于“纯类型注解注入（Type Hints DI）”的哲学，你只需要在服务里标注配置类的类型，框架自然会将全局唯一的配置对象塞给你：

```python
from canary_framework import service
from .config import AppConfig

@service()
class Database:
    cfg: AppConfig  # 框架会自动注入配置实例！

    async def startup(self):
        print(f"Connecting to {self.cfg.db_url}")
```
