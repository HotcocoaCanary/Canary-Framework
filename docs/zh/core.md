# Core 包

`canary_framework.core` 包提供框架基础：服务、模块、配置、生命周期和依赖注入。Core 包的一切与框架无关 —— 不涉及 Web 服务器，不涉及网络，纯粹是业务逻辑的装配。

## 装饰器速查

| 装饰器 | 用途 | 声明内容 |
|--------|------|----------|
| `@service` | 业务逻辑的最小单元 | `name`、`deps` |
| `@module` | 将服务组织成树状结构 | `name`、`services`、`deps` — 继承自 `@service` |
| `@on_config` | 在 wiring 之后、on_init 之前执行 | config 属性在此可用 |
| `@on_init` | 在配置加载后运行 | (无参数 — 依赖和配置是实例属性) |
| `@on_start` | 在 `app.start()` 时按拓扑序运行 | (无参数) |
| `@on_end` | 在 `app.stop()` 时按逆序运行 | (无参数) |


## 元数据类型（内部）

框架将装饰类的元数据以 dataclass 实例的形式存储在 `__cf_service_meta__` 上：

```
ServiceMeta              ModuleMeta (继承 ServiceMeta)    RouterMeta (继承 ServiceMeta)
├── name: str            ├── (继承所有字段)                ├── (继承所有字段)
├── deps: list[type]     └── services: list[type]          ├── prefix: str
└── config_cls: type|None                                  └── tags: list[str]
```

`@module` 和 `@router` 内部调用 `@service`，然后覆盖为各自更丰富的元数据类型。可通过 `isinstance(meta, ModuleMeta)` / `isinstance(meta, RouterMeta)` 区分。

## 快速示例

```python
from pydantic import BaseModel
from canary_framework import (
    Canary, service, module, on_config, on_init, on_start
)

class AppConfig(BaseModel):
    database_url: str = "sqlite://"

@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = connect(self.database_url)

    @on_start
    def start(self) -> None:
        self.pool.ping()

@module(name="app", services=[DBService])
class AppModule:
    pass

app = Canary(AppModule)
await app.config(config=AppConfig())
await app.init()
await app.start()
# ...
await app.stop()
```

## 延伸阅读

- [服务](./services.md) — 声明和使用服务
- [模块](./modules.md) — 将服务组合为模块
- [配置](./configuration.md) — pydantic BaseModel 配置系统
- [生命周期](./lifecycle.md) — config / init / start / end 钩子
- [依赖注入](./dependency-injection.md) — deps、命名和解析

