# Configuration

Configuration is runtime-root or Module context, not a dependency-injected Service and never a child.

## Declaration

```text
config() -> Callable[[type[CanaryConfig]], type[CanaryConfig]]
```

`config()` has no parameters. It returns a decorator that validates the target is a `CanaryConfig` subclass, marks it as framework configuration, and returns the same class. It does not wrap or instantiate the class; decorating a non-`CanaryConfig` class raises `TypeError`.

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

## `CanaryConfig` fields

| Field | Type and default | Meaning |
|---|---|---|
| `log_level` | `Literal[...] = "INFO"` | Framework logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `openapi_title` | `str = "Canary Framework API"` | OpenAPI document title. |
| `openapi_version` | `str = "1.0.0"` | API version written into the OpenAPI document. |
| `openapi_description` | `str = ""` | Optional OpenAPI document description. |
| `openapi_servers` | `list[dict[str, str]] = []` | OpenAPI server objects; use a default factory when overriding with mutable data. |
| `openapi_security_schemes` | `dict[str, dict[str, object]] = {}` | Root-owned OpenAPI security scheme definitions referenced by endpoint security names. |
| `docs_openapi_path` | `str = "/openapi.json"` | OpenAPI JSON endpoint. |
| `docs_swagger_path` | `str = "/docs"` | Swagger UI endpoint. |
| `docs_redoc_path` | `str = "/redoc"` | ReDoc endpoint. |
| `docs_swagger_css_cdn` | `str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"` | Stylesheet loaded by the generated Swagger page. |
| `docs_swagger_js_cdn` | `str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"` | Script loaded by the generated Swagger page. |
| `docs_redoc_cdn` | `str = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"` | Script loaded by the generated ReDoc page. |

`CanaryConfig` uses Pydantic Settings validation, allows application-specific extra fields, and does not load an environment file by default. The selected root or Module config instance propagates as context; it is not registered or injected as a Service.
