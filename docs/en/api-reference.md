# API Reference

Complete, source-verified API documentation for Canary Framework. The authoritative public
surface is `canary_framework.__all__`; this page documents every symbol exported there, plus the
documented base classes `ServiceBase` / `ModuleBase` / `Router` / `CanaryConfig` and their public
methods.

!!! tip "See also"
    This page is a signature reference. For narrative explanations and longer examples, see
    [Services](./services.md), [Modules](./modules.md), [Web / Routing](./web.md),
    [Configuration](./configuration.md), [Lifecycle](./lifecycle.md), and
    [Dependency Injection](./dependency-injection.md).

## Main exports

```python
from canary_framework import (
    # Decorators
    service, module, config,
    before_startup, before_shutdown,

    # Router
    Router,

    # Config
    CanaryConfig,

    # Exceptions
    CanaryFrameworkError,
    ConfigurationError,
    ServiceNotFoundError,
    CircularDependencyError,
    DependencyInjectionError,
    LifecycleHookError,

    # Lifecycle enum
    LifecycleHook,

    # Version
    __version__,
)
```

`ServiceBase` and `ModuleBase` are not re-exported from the top-level package — import them from
their `core` submodules:

```python
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
```

---

## Decorators

| Symbol | Signature | Description |
|---|---|---|
| `@service` | `service(*, config: type[CanaryConfig] \| None = None) -> Callable[[type], type[ServiceBase]]` | Marks a class as an injectable service. |
| `@module` | `module(*, services: list[type] \| None = None, config: type[CanaryConfig] \| None = None) -> Callable[[type], type[ModuleBase]]` | Marks a class as a module that composes child services. |
| `@config` | `config() -> Callable[[type], type[CanaryConfig]]` | Marks a `CanaryConfig` subclass so the framework can identify it. |
| `@before_startup` | `before_startup(func: HookFunction) -> HookFunction` | Marks a method to run during `startup()`. |
| `@before_shutdown` | `before_shutdown(func: HookFunction) -> HookFunction` | Marks a method to run during `shutdown()`. |

### @service { #service }

Declares a class as an injectable service. The class must inherit from `ServiceBase`. The
service's name is auto-generated as the class name (no `name=` parameter exists). Dependencies
are declared as bare class-level type annotations (see [Dependency Injection](./dependency-injection.md)),
not passed as a `deps=` argument.

```python
def service(
    *,
    config: type[CanaryConfig] | None = None,
) -> Callable[[type], type[ServiceBase]]
```

- `config` (keyword-only): an optional `CanaryConfig` subclass for this service. If omitted, the
  service inherits its parent module's config (propagated automatically, not via DI).

!!! example
    ```python
    from canary_framework import service
    from canary_framework.core.service import ServiceBase

    @service()
    class Database(ServiceBase):
        async def init(self) -> None:
            print("connecting…")
    ```

### @module { #module }

Declares a class as a module container. The class must inherit from `ModuleBase`. A module *is*
a service (it extends `ServiceBase` transitively via `ModuleBase`) that additionally orchestrates
child services through `init()` / `startup()` / `shutdown()`.

```python
def module(
    *,
    services: list[type] | None = None,
    config: type[CanaryConfig] | None = None,
) -> Callable[[type], type[ModuleBase]]
```

- `services` (keyword-only): the direct child services/sub-modules this module composes. Each
  entry must already be `@service`- or `@module`-decorated, or `module()` raises `TypeError`
  at decoration time.
- `config` (keyword-only): an optional `CanaryConfig` subclass for this module; propagated to
  children that don't declare their own.

!!! example
    ```python
    from canary_framework import module
    from canary_framework.core.module import ModuleBase

    @module(services=[Database, Auth, Api])
    class App(ModuleBase):
        pass
    ```

### @config { #config }

Marks a `CanaryConfig` subclass as a Canary Framework config class. The class must inherit from
`CanaryConfig`, or `config()` raises `TypeError` at decoration time.

```python
def config() -> Callable[[type], type[CanaryConfig]]
```

!!! example
    ```python
    from canary_framework import config
    from canary_framework import CanaryConfig

    @config()
    class AppConfig(CanaryConfig):
        log_level: str = "DEBUG"
    ```

### @before_startup / @before_shutdown { #lifecycle-hooks }

Mark a method to run during the corresponding lifecycle phase. Both accept sync or async
methods; `ServiceBase._invoke_hook` awaits coroutine functions and calls sync ones directly.

```python
def before_startup(func: HookFunction) -> HookFunction
def before_shutdown(func: HookFunction) -> HookFunction
```

!!! example
    ```python
    from canary_framework import service, before_shutdown
    from canary_framework.core.service import ServiceBase

    @service()
    class Database(ServiceBase):
        @before_shutdown
        async def disconnect(self) -> None:
            ...
    ```

See [Lifecycle](./lifecycle.md) for the full `init` → `startup` → `shutdown` sequencing.

---

## Base classes

### ServiceBase { #servicebase }

```python
from canary_framework.core.service import ServiceBase
```

The auto-injected base for `@service`-decorated classes. It is itself an ASGI application: its
`__call__` handles the `lifespan` protocol (dispatching to `startup`/`shutdown`) and delegates
all other scopes to `asgi_app`.

| Member | Signature | Description |
|---|---|---|
| `init` | `init() -> None` | Synchronous. Base implementation only logs; override to set up resources. |
| `startup` | `async startup() -> None` | Fires the `BEFORE_STARTUP` hook. |
| `shutdown` | `async shutdown() -> None` | Fires the `BEFORE_SHUTDOWN` hook. |
| `__call__` | `async __call__(scope, receive, send) -> None` | ASGI 3 entry point. |
| `asgi_app` | property → `starlette.routing.Router` | Lazily assembled, memoized Starlette router for this (sub)tree. |
| `openapi` | `openapi() -> dict[str, object]` | Returns the OpenAPI document for this (sub)tree, from the same memoized assembly as `asgi_app`. |
| `config` | property → `CanaryConfig \| None` | The config propagated from the parent module (or `None` if none was declared). |

!!! note "Single-point memoized assembly"
    Both `asgi_app` and `openapi()` are backed by one internal `_cf_assemble()` call, cached as
    `_cf_assembled`. The first access to either — which must happen **after** `init()` — collects
    the whole subtree's routes, checks for `(method, full_path)` collisions, and builds one
    Starlette routing table plus one OpenAPI document plus the doc endpoints. A standalone
    `@service` and a `@module`-composed subtree go through the exact same assembly path; only
    the collected subtree differs.

!!! example
    ```python
    import uvicorn
    from canary_framework.core.module import ModuleBase

    app = App()
    await app.init()
    uvicorn.run(app, lifespan="on")
    ```

### ModuleBase { #modulebase }

```python
from canary_framework.core.module import ModuleBase
```

Extends `ServiceBase`. Orchestrates child service lifecycle: instantiation, dependency
injection, and `init`/`startup`/`shutdown` in topological order.

| Member | Signature | Description |
|---|---|---|
| `init` | `init() -> None` | Registers children (recursively, with dependencies), topologically sorts them, instantiates + DI-wires each in order, then calls each child's `init()`. |
| `startup` | `async startup() -> None` | Fires `BEFORE_STARTUP`, then calls each child's `startup()` in topological order. |
| `shutdown` | `async shutdown() -> None` | Fires `BEFORE_SHUTDOWN`, then calls each child's `shutdown()` in **reverse** topological order. |
| `asgi_app` / `openapi` | *(inherited from `ServiceBase`)* | Assembles this module's own routes **plus** every descendant's routes into one routing table / OpenAPI document. |

!!! warning "Explicit prefixes, no auto-namespacing"
    There is no `/{ServiceName}` auto-mounting. A service whose `Router` has no `prefix` serves
    at the bare route path it declares. Give services an explicit `Router(prefix="/users")` to
    namespace them. A duplicate `(method, full_path)` anywhere in the tree raises `ValueError`
    when the tree is assembled.

---

## Router { #router }

```python
from canary_framework.core.router import Router
```

`Router` is a plain utility class (it does not extend `ServiceBase`) used as a class attribute
inside `@service`/`@module`-decorated classes to declare HTTP endpoints.

### Constructor

```python
class Router:
    def __init__(self, prefix: str = "", *, tags: list[str] | None = None) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prefix` | `str` | `""` | Path prefix prepended to every route registered on this router. |
| `tags` | `list[str] \| None` | `None` | OpenAPI tags applied to every route on this router. |

### HTTP method decorators

`get`, `post`, `put`, `delete`, and `patch` all share the same keyword-only parameters:

```python
def get(
    self,
    path: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    request_model: type | None = None,
    tags: list[str] | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[str, object] | None = None,
) -> Callable[[HookFunction], HookFunction]
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `str` (positional) | — | Route path. Query params are declared inline: `"/search?q={q}&page={page}"`. |
| `summary` | `str \| None` | `None` | OpenAPI summary. |
| `description` | `str \| None` | `None` | OpenAPI description. |
| `response_model` | `type \| None` | `None` | Pydantic model used **only** for OpenAPI docs — it does not validate or filter the actual response. |
| `request_model` | `type \| None` | `None` | Pydantic model for the request body. If omitted, a `BaseModel`-annotated handler parameter is auto-detected as the body. |
| `tags` | `list[str] \| None` | `None` | Extra OpenAPI tags for this route (merged with the router's tags). |
| `deprecated` | `bool` | `False` | Marks the route deprecated in OpenAPI. |
| `operation_id` | `str \| None` | `None` | OpenAPI `operationId`. |
| `responses` | `dict[str, object] \| None` | `None` | Additional OpenAPI response definitions. |

!!! warning "No `path_params` / `query_params` kwargs"
    Older drafts of this API accepted `path_params=`/`query_params=` kwargs. They do not exist —
    path and query parameter names are parsed automatically from the `path` string.

!!! note "Handlers take no `request` parameter"
    Parameters bind by **name**: names in `{...}` in the path are path params, names in the
    `?...={...}` query string are query params, and the first remaining parameter (optionally
    typed as a `BaseModel` subclass) is bound to the request body. A query parameter with a
    default that is *not* declared in the path string is never populated from the query string —
    it just keeps its default.

=== "GET with path + query params"
    ```python
    from canary_framework.core.router import Router
    from canary_framework.core.service import ServiceBase
    from canary_framework import service

    @service()
    class Users(ServiceBase):
        router = Router(prefix="/users", tags=["Users"])

        @router.get("/{user_id}")
        async def get_user(self, user_id: int):
            return {"id": user_id}

        @router.get("/search?q={q}&page={page}")
        async def search(self, q: str = "", page: int = 1):
            return {"q": q, "page": page}
    ```

=== "POST with a request body"
    ```python
    from pydantic import BaseModel

    class UserCreate(BaseModel):
        name: str

    @service()
    class Users(ServiceBase):
        router = Router(prefix="/users")

        @router.post("/", request_model=UserCreate)
        async def create_user(self, body: UserCreate):
            return (body, 201)
    ```

Return values are converted automatically (`_auto_response`): a `Response` passes through
as-is; a `(body, status_code)` tuple (where `status_code` is an `int` and not a `bool`) sets
that status; a `BaseModel`/`dict`/`list` becomes a `JSONResponse`; a `str` becomes
`PlainTextResponse`; anything else is stringified as `PlainTextResponse`.

See [Web / Routing](./web.md) for the full parameter-binding and status-code rules.

---

## CanaryConfig { #canaryconfig }

```python
from canary_framework import CanaryConfig
```

Base class for framework configuration (a `pydantic_settings.BaseSettings` subclass). Extra
fields are allowed, and environment variables matching field names (case-insensitive) override
defaults automatically. `.env` loading is disabled unless a subclass sets `env_file` in
`model_config`.

| Field | Type | Default | Description |
|---|---|---|---|
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` | Framework log level. |
| `openapi_title` | `str` | `"Canary Framework API"` | API title for the OpenAPI schema. |
| `openapi_version` | `str` | `"1.0.0"` | API version for the OpenAPI schema. |
| `openapi_description` | `str` | `""` | API description for the OpenAPI schema. |
| `openapi_servers` | `list[dict[str, str]]` | `[]` | OpenAPI `servers` entries. |
| `openapi_security_schemes` | `dict[str, dict[str, object]]` | `{}` | OpenAPI security scheme definitions. |
| `docs_openapi_path` | `str` | `"/openapi.json"` | Path serving the OpenAPI JSON document. |
| `docs_swagger_path` | `str` | `"/docs"` | Path serving the Swagger UI page. |
| `docs_redoc_path` | `str` | `"/redoc"` | Path serving the ReDoc page. |
| `docs_swagger_css_cdn` | `str` | jsDelivr Swagger UI CSS URL | Swagger UI CSS CDN URL. |
| `docs_swagger_js_cdn` | `str` | jsDelivr Swagger UI bundle URL | Swagger UI JS CDN URL. |
| `docs_redoc_cdn` | `str` | jsDelivr ReDoc bundle URL | ReDoc JS CDN URL. |

!!! example
    ```python
    from canary_framework import config, CanaryConfig

    @config()
    class AppConfig(CanaryConfig):
        log_level: str = "DEBUG"
        openapi_title: str = "My API"
    ```

See [Configuration](./configuration.md) for how config is attached to a module/service and
propagated to children.

---

## Data types { #data-types }

These live in `canary_framework.common.types` and are not part of the top-level `__all__`, but
are referenced by `Router`/`ServiceBase` public behavior (route collection, OpenAPI generation).

### RouteInfo

```python
@dataclass(slots=True)
class RouteInfo:
    handler: HookFunction
    method: str
    path: str
    starlette_path: str
    path_params: list[str]
    query_params: list[str]
    param_meta: dict[str, object]
    summary: str | None = None
    description: str | None = None
    response_model: type | None = None
    request_model: type | None = None
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    operation_id: str | None = None
    responses: dict[str, object] = field(default_factory=dict)
    router_prefix: str = ""
    router_tags: list[str] = field(default_factory=list)
    body_param: str | None = None
```

The complete, pre-parsed metadata for a single route, built by `Router.get`/`post`/etc. at
decoration time. `body_param` is the name of the handler parameter bound to the request body
(auto-detected or explicit via `request_model`).

### ResolvedRoute

```python
@dataclass(slots=True)
class ResolvedRoute:
    full_path: str
    handler: HookFunction
    info: RouteInfo
```

A fully-resolved route ready for assembly — the "aggregation currency" that
`_cf_collect_routes()` returns. `full_path` is the router's prefix already composed onto
`info.starlette_path` (repeated `//` normalized); `handler` is bound to the owning instance.

---

## Errors { #errors }

```python
from canary_framework import (
    CanaryFrameworkError,
    ConfigurationError,
    ServiceNotFoundError,
    CircularDependencyError,
    DependencyInjectionError,
    LifecycleHookError,
)
```

```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError       # config loading/validation failure
    ├── ServiceNotFoundError     # a requested service/module could not be located
    ├── CircularDependencyError  # topological sort detected a cycle
    ├── DependencyInjectionError # DI wiring failed at runtime
    └── LifecycleHookError       # a hook raised an unhandled exception
```

| Error | Raised when |
|---|---|
| `CanaryFrameworkError` | Base class for all framework errors — catch this to handle any of them. |
| `ConfigurationError` | Configuration loading or validation fails. |
| `ServiceNotFoundError` | A requested service or module cannot be located. |
| `CircularDependencyError` | `topological_sort()` detects a dependency cycle. |
| `DependencyInjectionError` | Dependency injection fails at runtime (e.g. a registered instance is `None`). |
| `LifecycleHookError` | A `@before_startup`/`@before_shutdown` hook raises; the original exception is chained via `__cause__`. |

---

## Version

```python
from canary_framework import __version__
```

`__version__: str` — the current installed version of Canary Framework.
