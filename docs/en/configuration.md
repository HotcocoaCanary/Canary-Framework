# Configuration

Canary Framework uses a Pydantic-based configuration system. All framework-configurable parameters are centralized in `CanaryConfig` with sensible defaults and type validation.

## CanaryConfig

`CanaryConfig(BaseModel)` provides all framework configuration fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | `"127.0.0.1"` | Server bind address |
| `port` | `int` | `8000` | Server port (1-65535) |
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` | Framework log level |
| `openapi_title` | `str` | `"Canary Framework API"` | API title for OpenAPI schema |
| `openapi_version` | `str` | `"1.0.0"` | API version for OpenAPI schema |
| `openapi_description` | `str` | `""` | API description for OpenAPI schema |
| `openapi_servers` | `list[dict[str,str]]` | `[]` | OpenAPI servers, e.g. `[{"url": "http://localhost:8000"}]` |
| `openapi_security_schemes` | `dict[str,dict[str,object]]` | `{}` | OpenAPI security schemes |
| `docs_openapi_path` | `str` | `"/openapi.json"` | OpenAPI JSON endpoint path |
| `docs_swagger_path` | `str` | `"/docs"` | Swagger UI path |
| `docs_redoc_path` | `str` | `"/redoc"` | ReDoc path |
| `docs_swagger_css_cdn` | `str` | Swagger CSS CDN URL | CSS CDN URL for Swagger UI |
| `docs_swagger_js_cdn` | `str` | Swagger JS CDN URL | JS CDN URL for Swagger UI |
| `docs_redoc_cdn` | `str` | ReDoc JS CDN URL | ReDoc CDN URL |

Extra fields are allowed via Pydantic's `model_config = {"extra": "allow"}` — you can add any custom configuration fields.

## Using @config

The `@config` decorator marks a class as the framework configuration. The class must inherit from `CanaryConfig`.

```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    openapi_title: str = "My Blog API"
    log_level: str = "DEBUG"
```

## Passing to configure()

Configuration is passed to the module's `configure()` method:

```python
async def setup():
    cfg = AppConfig()
    app = BlogApp()
    await app.configure(cfg)   # Must be CanaryConfig subclass or None
    await app.init()
    return app, cfg
```

`configure()` accepts only `CanaryConfig | None`. Passing other types raises `TypeError`:

```python
await app.configure({"host": "0.0.0.0"})  # TypeError: must be CanaryConfig subclass
```

## Configuration Field Groups

### Server

- **`host`** — Server bind address. Default `"127.0.0.1"`. Set to `"0.0.0.0"` to listen on all interfaces.
- **`port`** — Server port. Default `8000`. Must be in range 1-65535.

```python
@config
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
```

### Logging

- **`log_level`** — Framework log level. Valid values: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`. Default `"INFO"`.

The `"cf"` logger is automatically configured with a `StreamHandler` during `configure()` if no existing handlers are detected. The format is:

```
[YYYY-MM-DD HH:MM:SS] cf.module             INFO     Configuring module: AppModule
```

### OpenAPI Info

- **`openapi_title`** — API title shown in docs. Default `"Canary Framework API"`.
- **`openapi_version`** — API version. Default `"1.0.0"`.
- **`openapi_description`** — API description. Default `""`.
- **`openapi_servers`** — List of server URLs for the OpenAPI schema. Example: `[{"url": "http://localhost:8000"}]`.
- **`openapi_security_schemes`** — Security scheme definitions.

```python
@config
class AppConfig(CanaryConfig):
    openapi_title: str = "My API"
    openapi_version: str = "2.0.0"
    openapi_description: str = "A production-ready API"
    openapi_servers: list = [{"url": "http://localhost:8080"}]
```

### Documentation Endpoints

- **`docs_openapi_path`** — Path for the OpenAPI JSON endpoint. Default `"/openapi.json"`.
- **`docs_swagger_path`** — Path for Swagger UI. Default `"/docs"`.
- **`docs_redoc_path`** — Path for ReDoc. Default `"/redoc"`.
- **`docs_swagger_css_cdn`** / **`docs_swagger_js_cdn`** — CDN URLs for Swagger UI assets.
- **`docs_redoc_cdn`** — CDN URL for ReDoc assets.

```python
@config
class AppConfig(CanaryConfig):
    docs_swagger_path: str = "/swagger"
    docs_redoc_path: str = "/documentation"
    docs_openapi_path: str = "/api/schema.json"
```

## Custom Fields

Add any custom configuration fields to your config class. Pydantic's `model_config = {"extra": "allow"}` accepts arbitrary extra fields:

```python
@config
class AppConfig(CanaryConfig):
    database_url: str = "sqlite:///app.db"  # Custom field
    api_key: str = ""                       # Custom field
    debug: bool = False                     # Custom field

@service()
class Database(ServiceBase):
    @after_config
    async def connect(self):
        url = self.config.database_url  # Access custom field
        self.pool = await connect(url)
```

Custom fields are accessed via `self.config.<field_name>` in any service, router, or module that has been configured.
