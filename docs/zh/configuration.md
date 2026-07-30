# 配置

配置属于运行根或 Module 上下文，不是依赖注入 Service，也不能放进 children。

## 声明

```text
config() -> Callable[[type[CanaryConfig]], type[CanaryConfig]]
```

`config()` 没有参数。它返回一个装饰器，校验目标是否为 `CanaryConfig` 子类，将其标记为框架配置类，并原样返回该类。它不会包装或实例化类；装饰非 `CanaryConfig` 类会抛出 `TypeError`。

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

## `CanaryConfig` 字段

| 字段 | 类型与默认值 | 含义 |
|---|---|---|
| `log_level` | `Literal[...] = "INFO"` | 框架日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR` 或 `CRITICAL`。 |
| `openapi_title` | `str = "Canary Framework API"` | OpenAPI 文档标题。 |
| `openapi_version` | `str = "1.0.0"` | 写入 OpenAPI 文档的 API 版本。 |
| `openapi_description` | `str = ""` | 可选 OpenAPI 文档描述。 |
| `openapi_servers` | `list[dict[str, str]] = []` | OpenAPI server 对象；覆盖可变数据时使用 default factory。 |
| `openapi_security_schemes` | `dict[str, dict[str, object]] = {}` | 由运行根拥有、供端点 security 名称引用的 OpenAPI 安全方案定义。 |
| `docs_openapi_path` | `str = "/openapi.json"` | OpenAPI JSON 端点。 |
| `docs_swagger_path` | `str = "/docs"` | Swagger UI 端点。 |
| `docs_redoc_path` | `str = "/redoc"` | ReDoc 端点。 |
| `docs_swagger_css_cdn` | `str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"` | 生成的 Swagger 页面加载的样式表。 |
| `docs_swagger_js_cdn` | `str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"` | 生成的 Swagger 页面加载的脚本。 |
| `docs_redoc_cdn` | `str = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"` | 生成的 ReDoc 页面加载的脚本。 |

`CanaryConfig` 使用 Pydantic Settings 校验，允许应用自定义额外字段，默认不加载环境文件。运行根或 Module 选定的配置实例作为上下文向下传播，不会注册或注入为 Service。
