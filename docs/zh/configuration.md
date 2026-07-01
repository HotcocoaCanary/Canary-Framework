# 配置

Canary Framework 使用基于 Pydantic 的配置系统。所有框架可配置参数集中在 `CanaryConfig` 中，具有合理的默认值和类型验证。

## CanaryConfig

`CanaryConfig(BaseModel)` 提供所有框架配置字段：

| 字段 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| `host` | `str` | `"127.0.0.1"` | 服务器绑定地址 |
| `port` | `int` | `8000` | 服务器端口 (1-65535) |
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` | 框架日志级别 |
| `openapi_title` | `str` | `"Canary Framework API"` | OpenAPI schema 的 API 标题 |
| `openapi_version` | `str` | `"1.0.0"` | OpenAPI schema 的 API 版本 |
| `openapi_description` | `str` | `""` | OpenAPI schema 的 API 描述 |
| `openapi_servers` | `list[dict[str,str]]` | `[]` | OpenAPI 服务器，如 `[{"url": "http://localhost:8000"}]` |
| `openapi_security_schemes` | `dict[str,dict[str,object]]` | `{}` | OpenAPI 安全方案 |
| `docs_openapi_path` | `str` | `"/openapi.json"` | OpenAPI JSON 端点路径 |
| `docs_swagger_path` | `str` | `"/docs"` | Swagger UI 路径 |
| `docs_redoc_path` | `str` | `"/redoc"` | ReDoc 路径 |
| `docs_swagger_css_cdn` | `str` | Swagger CSS CDN URL | Swagger UI 的 CSS CDN URL |
| `docs_swagger_js_cdn` | `str` | Swagger JS CDN URL | Swagger UI 的 JS CDN URL |
| `docs_redoc_cdn` | `str` | ReDoc JS CDN URL | ReDoc CDN URL |

通过 Pydantic 的 `model_config = {"extra": "allow"}` 允许额外字段 — 您可以添加任意自定义配置字段。

## 使用 @config

`@config` 装饰器将类标记为框架配置。该类必须继承 `CanaryConfig`。

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    openapi_title: str = "My Blog API"
    log_level: str = "DEBUG"
```

## 将 Config 作为服务使用

Config 是普通的 DI 服务。将其加入模块的 `services` 列表并通过注解注入：

```python
@module(services=[AppConfig, Database, Posts])
class BlogApp(ModuleBase):
    config: AppConfig

async def setup():
    app = BlogApp()
    await app.init()   # Config 通过 issubclass(CanaryConfig) 从 services 自动发现
    return app
```

Config 通过 `@module(services=[...])` 自动发现 —— 任何通过 `issubclass(CanaryConfig)` 检查的类均被视为配置。

## 配置字段分组

### 服务器

- **`host`** — 服务器绑定地址。默认 `"127.0.0.1"`。设置为 `"0.0.0.0"` 以监听所有接口。
- **`port`** — 服务器端口。默认 `8000`。必须在 1-65535 范围内。

```python
@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
```

### 日志

- **`log_level`** — 框架日志级别。有效值：`"DEBUG"`、`"INFO"`、`"WARNING"`、`"ERROR"`、`"CRITICAL"`。默认 `"INFO"`。

如果未检测到现有处理器，`"cf"` 日志器会在 `init()` 期间自动配置 `StreamHandler`。格式为：

```
[YYYY-MM-DD HH:MM:SS] cf.module             INFO     Initializing module: AppModule
```

### OpenAPI 信息

- **`openapi_title`** — 文档中显示的 API 标题。默认 `"Canary Framework API"`。
- **`openapi_version`** — API 版本。默认 `"1.0.0"`。
- **`openapi_description`** — API 描述。默认 `""`。
- **`openapi_servers`** — OpenAPI schema 的服务器 URL 列表。示例：`[{"url": "http://localhost:8000"}]`。
- **`openapi_security_schemes`** — 安全方案定义。

```python
@config()
class AppConfig(CanaryConfig):
    openapi_title: str = "My API"
    openapi_version: str = "2.0.0"
    openapi_description: str = "A production-ready API"
    openapi_servers: list = [{"url": "http://localhost:8080"}]
```

### 文档端点 {#docs-endpoints}

- **`docs_openapi_path`** — OpenAPI JSON 端点的路径。默认 `"/openapi.json"`。
- **`docs_swagger_path`** — Swagger UI 的路径。默认 `"/docs"`。
- **`docs_redoc_path`** — ReDoc 的路径。默认 `"/redoc"`。
- **`docs_swagger_css_cdn`** / **`docs_swagger_js_cdn`** — Swagger UI 资源的 CDN URL。
- **`docs_redoc_cdn`** — ReDoc 资源的 CDN URL。

```python
@config()
class AppConfig(CanaryConfig):
    docs_swagger_path: str = "/swagger"
    docs_redoc_path: str = "/documentation"
    docs_openapi_path: str = "/api/schema.json"
```

## 自定义字段

在配置类中添加任意自定义配置字段。Pydantic 的 `model_config = {"extra": "allow"}` 接受任意额外字段：

```python
@config()
class AppConfig(CanaryConfig):
    database_url: str = "sqlite:///app.db"  # 自定义字段
    api_key: str = ""                       # 自定义字段
    debug: bool = False                     # 自定义字段

@service()
class Database(ServiceBase):
    config: AppConfig

    async def init(self):
        await super().init()
        url = self.config.database_url  # 通过注入的 config 访问自定义字段
        self.pool = await connect(url)
```

Config 字段通过注入的 `self.config` 属性在任何服务、路由或模块中访问。
