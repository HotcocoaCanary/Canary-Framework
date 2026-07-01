# API 参考

Canary Framework 的完整、经源码校验的 API 文档。权威的公共接口以 `canary_framework.__all__`
为准；本页记录该列表中导出的每一个符号，以及已文档化的基类 `ServiceBase` / `ModuleBase` /
`Router` / `CanaryConfig` 及其公共方法。

!!! tip "另请参阅"
    本页是签名参考。关于叙述性说明和更完整的示例，请参阅
    [Services](./services.md)、[Modules](./modules.md)、[Web / Routing](./web.md)、
    [Configuration](./configuration.md)、[Lifecycle](./lifecycle.md) 以及
    [Dependency Injection](./dependency-injection.md)。

## 主要导出

```python
from canary_framework import (
    # 装饰器
    service, module, config,
    before_startup, before_shutdown,

    # Router
    Router,

    # Config
    CanaryConfig,

    # 异常
    CanaryFrameworkError,
    ConfigurationError,
    ServiceNotFoundError,
    CircularDependencyError,
    DependencyInjectionError,
    LifecycleHookError,

    # 生命周期枚举
    LifecycleHook,

    # 版本
    __version__,
)
```

`ServiceBase` 和 `ModuleBase` 并未从顶层包重新导出——需从各自的 `core` 子模块导入：

```python
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
```

---

## 装饰器

| 符号 | 签名 | 描述 |
|---|---|---|
| `@service` | `service(*, config: type[CanaryConfig] \| None = None) -> Callable[[type], type[ServiceBase]]` | 将类标记为可注入的服务。 |
| `@module` | `module(*, services: list[type] \| None = None, config: type[CanaryConfig] \| None = None) -> Callable[[type], type[ModuleBase]]` | 将类标记为组合子服务的模块。 |
| `@config` | `config() -> Callable[[type], type[CanaryConfig]]` | 标记一个 `CanaryConfig` 子类，使框架能够识别它。 |
| `@before_startup` | `before_startup(func: HookFunction) -> HookFunction` | 标记一个在 `startup()` 期间执行的方法。 |
| `@before_shutdown` | `before_shutdown(func: HookFunction) -> HookFunction` | 标记一个在 `shutdown()` 期间执行的方法。 |

### @service { #service }

将一个类声明为可注入服务。该类必须继承自 `ServiceBase`。服务名称自动生成为类名（不存在
`name=` 参数）。依赖通过类体上的裸类型注解声明（见 [Dependency Injection](./dependency-injection.md)），
而非通过 `deps=` 参数传入。

```python
def service(
    *,
    config: type[CanaryConfig] | None = None,
) -> Callable[[type], type[ServiceBase]]
```

- `config`（仅关键字参数）：该服务可选的 `CanaryConfig` 子类。如果省略，服务将继承其父模块的
  config（自动传播，而非通过 DI）。

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

将一个类声明为模块容器。该类必须继承自 `ModuleBase`。模块本身*就是*一个服务（通过
`ModuleBase` 间接继承自 `ServiceBase`），并额外通过 `init()` / `startup()` / `shutdown()`
编排子服务。

```python
def module(
    *,
    services: list[type] | None = None,
    config: type[CanaryConfig] | None = None,
) -> Callable[[type], type[ModuleBase]]
```

- `services`（仅关键字参数）：此模块组合的直接子服务/子模块。每一项都必须已经用 `@service`
  或 `@module` 装饰，否则 `module()` 会在装饰时抛出 `TypeError`。
- `config`（仅关键字参数）：该模块可选的 `CanaryConfig` 子类；会传播给未声明自身 config 的
  子服务。

!!! example
    ```python
    from canary_framework import module
    from canary_framework.core.module import ModuleBase

    @module(services=[Database, Auth, Api])
    class App(ModuleBase):
        pass
    ```

### @config { #config }

将一个 `CanaryConfig` 子类标记为 Canary Framework 配置类。该类必须继承自 `CanaryConfig`，
否则 `config()` 会在装饰时抛出 `TypeError`。

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

标记一个方法在对应的生命周期阶段执行。两者都接受同步或异步方法；
`ServiceBase._invoke_hook` 会 await 协程函数，直接调用同步函数。

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

完整的 `init` → `startup` → `shutdown` 时序请参阅 [Lifecycle](./lifecycle.md)。

---

## 基类

### ServiceBase { #servicebase }

```python
from canary_framework.core.service import ServiceBase
```

`@service` 装饰类的自动注入基类。它本身就是一个 ASGI 应用：其 `__call__` 处理 `lifespan`
协议（分发到 `startup`/`shutdown`），并将其余所有 scope 委托给 `asgi_app`。

| 成员 | 签名 | 描述 |
|---|---|---|
| `init` | `init() -> None` | 同步方法。基类实现仅记录日志；可重写以设置资源。 |
| `startup` | `async startup() -> None` | 触发 `BEFORE_STARTUP` 钩子。 |
| `shutdown` | `async shutdown() -> None` | 触发 `BEFORE_SHUTDOWN` 钩子。 |
| `__call__` | `async __call__(scope, receive, send) -> None` | ASGI 3 入口点。 |
| `asgi_app` | 属性 → `starlette.routing.Router` | 该（子）树懒加载、记忆化组装的 Starlette 路由器。 |
| `openapi` | `openapi() -> dict[str, object]` | 返回该（子）树的 OpenAPI 文档，来自与 `asgi_app` 相同的记忆化组装。 |
| `config` | 属性 → `CanaryConfig \| None` | 由父模块传播下来的 config（如果未声明则为 `None`）。 |

!!! note "单点记忆化组装"
    `asgi_app` 和 `openapi()` 都由同一个内部 `_cf_assemble()` 调用支撑，结果缓存为
    `_cf_assembled`。二者中任意一个的首次访问——必须发生在 `init()` **之后**——会收集整个子树
    的路由，检查 `(method, full_path)` 冲突，并构建一张 Starlette 路由表、一份 OpenAPI 文档，
    以及文档端点。独立运行的 `@service` 和由 `@module` 装配的子树走的是完全相同的组装路径，
    区别仅在于被收集的子树范围不同。

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

继承自 `ServiceBase`。编排子服务的生命周期：实例化、依赖注入，以及按拓扑顺序执行
`init`/`startup`/`shutdown`。

| 成员 | 签名 | 描述 |
|---|---|---|
| `init` | `init() -> None` | 递归注册子服务（含其依赖），拓扑排序，按序实例化并完成 DI 注入，然后调用每个子服务的 `init()`。 |
| `startup` | `async startup() -> None` | 触发 `BEFORE_STARTUP`，然后按拓扑顺序调用每个子服务的 `startup()`。 |
| `shutdown` | `async shutdown() -> None` | 触发 `BEFORE_SHUTDOWN`，然后按**逆**拓扑顺序调用每个子服务的 `shutdown()`。 |
| `asgi_app` / `openapi` | *（继承自 `ServiceBase`）* | 将该模块自身的路由**与**所有后代的路由组装为一张路由表 / 一份 OpenAPI 文档。 |

!!! warning "显式前缀，无自动命名空间"
    不存在 `/{ServiceName}` 自动挂载。若某服务的 `Router` 未设置 `prefix`，它将直接在其声明的
    裸路径上提供服务。请为服务设置显式的 `Router(prefix="/users")` 以实现命名空间隔离。树中
    任意位置出现重复的 `(method, full_path)`，都会在组装整棵树时抛出 `ValueError`。

---

## Router { #router }

```python
from canary_framework.core.router import Router
```

`Router` 是一个普通的工具类（不继承 `ServiceBase`），作为类属性用在 `@service`/`@module`
装饰的类内部，用于声明 HTTP 端点。

### 构造器

```python
class Router:
    def __init__(self, prefix: str = "", *, tags: list[str] | None = None) -> None
```

| 参数 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| `prefix` | `str` | `""` | 附加到该 router 上注册的每条路由前的路径前缀。 |
| `tags` | `list[str] \| None` | `None` | 应用于该 router 上每条路由的 OpenAPI 标签。 |

### HTTP 方法装饰器

`get`、`post`、`put`、`delete`、`patch` 共用相同的仅关键字参数：

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

| 参数 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| `path` | `str`（位置参数） | — | 路由路径。查询参数需内联声明：`"/search?q={q}&page={page}"`。 |
| `summary` | `str \| None` | `None` | OpenAPI 摘要。 |
| `description` | `str \| None` | `None` | OpenAPI 描述。 |
| `response_model` | `type \| None` | `None` | 仅用于 OpenAPI 文档的 Pydantic 模型——**不会**校验或过滤实际响应。 |
| `request_model` | `type \| None` | `None` | 请求体的 Pydantic 模型。若省略，将自动探测被标注为 `BaseModel` 子类的处理器参数作为请求体。 |
| `tags` | `list[str] \| None` | `None` | 该路由额外的 OpenAPI 标签（与 router 的标签合并）。 |
| `deprecated` | `bool` | `False` | 在 OpenAPI 中标记该路由为已弃用。 |
| `operation_id` | `str \| None` | `None` | OpenAPI 的 `operationId`。 |
| `responses` | `dict[str, object] \| None` | `None` | 额外的 OpenAPI 响应定义。 |

!!! warning "不存在 `path_params` / `query_params` 参数"
    该 API 的早期草案曾接受 `path_params=`/`query_params=` 参数。它们并不存在——路径与查询
    参数名会从 `path` 字符串中自动解析。

!!! note "处理器不接收 `request` 参数"
    参数按**名称**绑定：路径中 `{...}` 内的名称为路径参数，查询字符串 `?...={...}` 中的名称
    为查询参数，剩余的第一个参数（可选地标注为 `BaseModel` 子类）绑定为请求体。**未**在路径
    字符串中声明的带默认值查询参数永远不会从查询字符串中获取——它只是保留其默认值。

=== "GET：路径参数 + 查询参数"
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

=== "POST：带请求体"
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

返回值会被自动转换（`_auto_response`）：`Response` 原样返回；`(body, status_code)` 二元组
（`status_code` 为 `int` 且非 `bool`）会设置该状态码；`BaseModel`/`dict`/`list` 转为
`JSONResponse`；`str` 转为 `PlainTextResponse`；其他类型转字符串后以 `PlainTextResponse`
返回。

完整的参数绑定与状态码规则请参阅 [Web / Routing](./web.md)。

---

## CanaryConfig { #canaryconfig }

```python
from canary_framework import CanaryConfig
```

框架配置的基类（`pydantic_settings.BaseSettings` 的子类）。允许额外字段，且与字段名匹配的
环境变量（大小写不敏感）会自动覆盖默认值。除非子类在 `model_config` 中设置 `env_file`，
否则 `.env` 加载默认关闭。

| 字段 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` | 框架日志级别。 |
| `openapi_title` | `str` | `"Canary Framework API"` | OpenAPI schema 的 API 标题。 |
| `openapi_version` | `str` | `"1.0.0"` | OpenAPI schema 的 API 版本。 |
| `openapi_description` | `str` | `""` | OpenAPI schema 的 API 描述。 |
| `openapi_servers` | `list[dict[str, str]]` | `[]` | OpenAPI 的 `servers` 条目。 |
| `openapi_security_schemes` | `dict[str, dict[str, object]]` | `{}` | OpenAPI 安全方案定义。 |
| `docs_openapi_path` | `str` | `"/openapi.json"` | 提供 OpenAPI JSON 文档的路径。 |
| `docs_swagger_path` | `str` | `"/docs"` | 提供 Swagger UI 页面的路径。 |
| `docs_redoc_path` | `str` | `"/redoc"` | 提供 ReDoc 页面的路径。 |
| `docs_swagger_css_cdn` | `str` | jsDelivr Swagger UI CSS URL | Swagger UI CSS CDN URL。 |
| `docs_swagger_js_cdn` | `str` | jsDelivr Swagger UI bundle URL | Swagger UI JS CDN URL。 |
| `docs_redoc_cdn` | `str` | jsDelivr ReDoc bundle URL | ReDoc JS CDN URL。 |

!!! example
    ```python
    from canary_framework import config, CanaryConfig

    @config()
    class AppConfig(CanaryConfig):
        log_level: str = "DEBUG"
        openapi_title: str = "My API"
    ```

config 如何附加到模块/服务并传播给子服务，请参阅 [Configuration](./configuration.md)。

---

## 数据类型 { #data-types }

以下类型位于 `canary_framework.common.types`，不属于顶层 `__all__`，但被 `Router`/
`ServiceBase` 的公共行为（路由收集、OpenAPI 生成）所引用。

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

单条路由的完整、预解析元数据，由 `Router.get`/`post` 等方法在装饰时构建。`body_param` 是
绑定到请求体的处理器参数名（自动探测，或通过 `request_model` 显式指定）。

### ResolvedRoute

```python
@dataclass(slots=True)
class ResolvedRoute:
    full_path: str
    handler: HookFunction
    info: RouteInfo
```

已解析、可直接组装的路由——即 `_cf_collect_routes()` 返回的“聚合货币”。`full_path` 是已将
router 前缀拼接到 `info.starlette_path` 上的结果（重复的 `//` 会被规范化）；`handler` 已绑定
到拥有它的实例。

---

## 错误 { #errors }

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
    ├── ConfigurationError       # 配置加载/校验失败
    ├── ServiceNotFoundError     # 请求的服务/模块无法定位
    ├── CircularDependencyError  # 拓扑排序检测到循环
    ├── DependencyInjectionError # 运行时 DI 注入失败
    └── LifecycleHookError       # 钩子抛出未处理异常
```

| 错误 | 触发时机 |
|---|---|
| `CanaryFrameworkError` | 所有框架错误的基类——捕获它即可处理任意框架错误。 |
| `ConfigurationError` | 配置加载或校验失败时。 |
| `ServiceNotFoundError` | 请求的服务或模块无法定位时。 |
| `CircularDependencyError` | `topological_sort()` 检测到依赖循环时。 |
| `DependencyInjectionError` | 依赖注入在运行时失败时（例如已注册的实例为 `None`）。 |
| `LifecycleHookError` | `@before_startup`/`@before_shutdown` 钩子抛出异常时；原始异常通过 `__cause__` 链接。 |

---

## 版本

```python
from canary_framework import __version__
```

`__version__: str` —— 当前已安装 Canary Framework 的版本号。
