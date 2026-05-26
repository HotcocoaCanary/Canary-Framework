# Core 包

`canary_framework.core` 包提供框架基础：服务、模块、配置、生命周期和依赖注入。Core 包的一切与框架无关 —— 不涉及 Web 服务器，不涉及网络，纯粹是业务逻辑的装配。

## 装饰器速查

| 装饰器 | 用途 | 声明内容 |
|--------|------|----------|
| `@service` | 业务逻辑的最小单元 | `name`、`deps`、`config` |
| `@module` | 将服务组织成树状结构 | `name`、`services`、`deps`、`config` — 继承自 `@service` |
| `@config` | 将普通类转为 pydantic-settings 模型 | 带类型注解和默认值的字段 |
| `@on_init` | 在 DI + 配置就绪后运行 | (无参数 — 依赖和配置是实例属性) |
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
from canary_framework import (
    Canary, config, service, module, on_init, on_start
)

@config
class AppConfig:
    database_url: str = "sqlite://"

@service(name="db", config=AppConfig)
class DBService:
    app_config: AppConfig

    @on_init
    def init(self) -> None:
        self.pool = connect(self.app_config.database_url)

    @on_start
    def start(self) -> None:
        self.pool.ping()

@module(name="app", config=AppConfig, services=[DBService])
class AppModule:
    pass

app = Canary(AppModule)
await app.init()
await app.start()
# ...
await app.stop()
```

## 延伸阅读

- [服务](./services.md) — 声明和使用服务
- [模块](./modules.md) — 将服务组合为模块
- [配置](./configuration.md) — @config 与配置继承
- [生命周期](./lifecycle.md) — init / start / end 钩子
- [依赖注入](./dependency-injection.md) — deps、命名和解析

