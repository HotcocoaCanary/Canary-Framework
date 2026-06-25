# API 参考

Canary Framework 的完整 API 文档。

## 主要导出

```python
from canary_framework import (
    # 装饰器
    config, service, module,
    before_startup, before_shutdown,

    # Router
    Router,

    # Config
    CanaryConfig,

    # 异常
    CanaryFrameworkError,
    DependencyInjectionError,
    CircularDependencyError,
    ConfigurationError,
    CanaryFrameworkError,
    ServiceNotFoundError,

    # 枚举
    LifecycleHook,

    # 版本
    __version__,
)
```

`ServiceBase` 和 `ModuleBase` 从 `canary_framework.core` 导入：

```python
from canary_framework.core.service import ServiceBase
from canary_framework.core.module import ModuleBase
```

---

## 装饰器

### @service

将类标记为服务。

**签名：**
```python
def service() -> Callable[[type], type[ServiceBase]]
```

**参数：**
- 无。`name` 和 `deps` 参数已移除。

服务名称自动生成为 `ClassName` + `"Service"`。依赖通过类体上的类型注解声明。

**示例：**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    pass
```

---

### @module

将类标记为模块容器。

**签名：**
```python
def module(
    *,
    services: list[type] | None = None,
) -> Callable[[type], type[ModuleBase]]
```

**参数：**
- `services`（list[type]，仅关键字）：此模块包含的服务、路由和子模块

`name` 和 `deps` 参数已移除。模块名称自动生成为 `ClassName` + `"Module"`。

**示例：**
```python
from canary_framework import module
from canary_framework.core.module import ModuleBase

@module(services=[Database, Auth, Api])
class App(ModuleBase):
    pass
```

---

### Router

路由管理器，作为类属性在 `@service()` 或 `@module()` 装饰类中使用。

**签名：**
```python
class Router:
    def __init__(self, prefix: str = "", *, tags: list[str] | None = None)
```

**参数：**
- `prefix`（str，默认 `""`）：应用于此 Router 中所有路由的 URL 前缀
- `tags`（list[str] | None）：用于文档分组的 OpenAPI 标签

**示例：**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["API"])

    @router.get("/users/{user_id}")
    async def get_user(self, user_id: int): ...
```

---

### Router HTTP 方法装饰器

Router 实例提供用于定义路由的方法装饰器：`@router.get`、`@router.post`、`@router.put`、`@router.delete`、`@router.patch`。

**方法签名：**
```python
def get(path: str, *, summary=None, description=None, response_model=None,
        request_model=None, tags=None, deprecated=False, operation_id=None,
        responses=None, path_params=None, query_params=None) -> Callable
def post(...)  # 相同参数
def put(...)   # 相同参数
def delete(...)  # 相同参数
def patch(...)  # 相同参数
```

**参数与之前相同**，但现在作为 `@router.get()`、`@router.post()` 等方法调用，而非独立的 `@get()`、`@post()`。

路由处理器**不**接收 `request` 参数。路径参数、查询参数和请求体自动绑定。

**示例：**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        pass

    @router.post("/", request_model=UserCreate)
    async def create_user(self, body: UserCreate):
        pass
```

---

### @config

将类标记为配置类。

**签名：**
```python
def config() -> Callable[[type], type[CanaryConfig]]
```

**参数：** 无。

配置类必须继承 `CanaryConfig`。在类上设置 `CF_CONFIG_MARKER`。

**示例：**
```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config()
class AppConfig(CanaryConfig):
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "DEBUG"
```

---

### 生命周期钩子装饰器

将方法标记为生命周期钩子。

**签名：**
```python
def before_startup(func) -> HookFunction
def before_shutdown(func) -> HookFunction
```

**示例：**
```python
from canary_framework import service, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    async def init(self):
        await super().init()
        # 建立连接

    async def shutdown(self):\n        await super().shutdown()
    async def disconnect(self):
        pass
```

---

## 基类

### CanaryConfig

框架配置的基类。所有配置类必须继承 `CanaryConfig`。

```python
from canary_framework.common.config import CanaryConfig
```

**字段（均可选，含默认值）：**

| 字段 | 类型 | 默认值 | 描述 |
|-------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | 服务器绑定地址 |
| `port` | `int` | `8000` | 服务器端口 (1-65535) |
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` | 框架日志级别 |
| `openapi_title` | `str` | `"Canary Framework API"` | OpenAPI schema 的 API 标题 |
| `openapi_version` | `str` | `"1.0.0"` | OpenAPI schema 的 API 版本 |
| `openapi_description` | `str` | `""` | OpenAPI schema 的 API 描述 |
| `openapi_servers` | `list[dict[str,str]]` | `[]` | OpenAPI 服务器 URL |
| `openapi_security_schemes` | `dict[str,dict[str,object]]` | `{}` | OpenAPI 安全方案 |
| `docs_openapi_path` | `str` | `"/openapi.json"` | OpenAPI JSON 端点路径 |
| `docs_swagger_path` | `str` | `"/docs"` | Swagger UI 路径 |
| `docs_redoc_path` | `str` | `"/redoc"` | ReDoc 路径 |
| `docs_swagger_css_cdn` | `str` | Swagger CSS CDN URL | CSS CDN URL |
| `docs_swagger_js_cdn` | `str` | Swagger JS CDN URL | JS CDN URL |
| `docs_redoc_cdn` | `str` | ReDoc JS CDN URL | ReDoc CDN URL |

允许额外字段 — 您可以添加任意自定义配置字段。

---

### ServiceBase

服务的基类。

**导入：**
```python
from canary_framework.core.service import ServiceBase
```

**属性：**
- `_cf_hooks`：内部钩子注册表（懒加载）
- `_cf_parent_registry`：父注册表引用（由父模块设置）

**方法：**
- `async init()`：初始化服务。设置日志和配置。
- `async startup()`：启动服务。调用 `BEFORE_STARTUP` 钩子。
- `async shutdown()`：关闭服务。调用 `BEFORE_SHUTDOWN` 钩子。
- `async __call__(scope, receive, send)`：ASGI 3 接口。处理 lifespan 事件并将其他请求委托给 `self.asgi_app`。
- `async _handle_lifespan(receive, send)`：内部 ASGI lifespan 协议处理器。
- `async _invoke_hook(hook: LifecycleHook)`：懒加载钩子发现和调用。

---

### ModuleBase

模块的基类，扩展 `ServiceBase`。

**导入：**
```python
from canary_framework.core.module import ModuleBase
```

**属性：**
- `_cf_parent_registry`：父注册表（如果有）
- `_cf_registry`：此模块的服务注册表
- `_cf_startup_order`：拓扑顺序的服务名称列表
- `_cf_asgi_app`：缓存的 ASGI Starlette Router（懒加载构建）

**属性（只读）：**
- `asgi_app`：带有已挂载子 ASGI 应用和根路由的 Starlette `Router`

**方法：**
- `async init()`：递归注册服务、拓扑排序、实例化、DI 注入、初始化子服务。Config 通过 `issubclass(CanaryConfig)` 从 services 列表自动发现。
- `async startup()`：按拓扑顺序启动模块和所有子服务
- `async shutdown()`：按逆拓扑顺序关闭模块和所有子服务
- `_register_entry_with_deps(cls, registry)`：递归注册服务及其注解解析的依赖

---

### Router

路由管理器类，作为类属性在 `@service()` 或 `@module()` 装饰类中使用。
不继承 `ServiceBase` — 它是一个独立的工具类。

**导入：**
```python
from canary_framework.core.router import Router
```

**构造器：**
```python
class Router:
    def __init__(self, prefix: str = "", *, tags: list[str] | None = None)
```

**参数：**
- `prefix`（str，默认 `""`）：应用于此 Router 中所有路由的 URL 前缀
- `tags`（list[str] | None）：用于文档分组的 OpenAPI 标签

**方法：**
- `get(path, *, summary=None, description=None, response_model=None, request_model=None, tags=None, deprecated=False, operation_id=None, responses=None, path_params=None, query_params=None) -> Callable`：GET 路由装饰器
- `post(...)`：POST 路由装饰器（相同参数）
- `put(...)`：PUT 路由装饰器（相同参数）
- `delete(...)`：DELETE 路由装饰器（相同参数）
- `patch(...)`：PATCH 路由装饰器（相同参数）

**示例：**
```python
from canary_framework import service
from canary_framework.core.service import ServiceBase
from canary_framework.core.router import Router

@service()
class Api(ServiceBase):
    router = Router(prefix="/api", tags=["API"])

    @router.get("/users/{user_id}")
    async def get_user(self, user_id: int): ...
```

---

## 枚举

### LifecycleHook

生命周期钩子阶段。

**值：**
- `LifecycleHook.BEFORE_STARTUP`：`"before_startup"`
- `LifecycleHook.BEFORE_SHUTDOWN`：`"before_shutdown"`

---

## 异常

### CanaryFrameworkError

所有框架错误的基础异常。

**层次结构：**
```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError       # 配置加载/验证失败
    ├── ServiceNotFoundError     # 服务查找失败
    ├── CircularDependencyError  # 拓扑排序检测到循环
    ├── DependencyInjectionError # DI 注入失败
    └── CanaryFrameworkError       # 钩子引发未处理异常
```

---

### DependencyInjectionError

依赖注入期间发生错误。

---

### CircularDependencyError

拓扑排序期间检测到循环依赖。

---

### CanaryFrameworkError

生命周期钩子中发生错误。包装原始异常。

---

### ServiceNotFoundError

注册表中未找到服务。

---

### ConfigurationError

配置验证或加载错误。

---

## 通用模块

### 标记 (Markers)

用于标识框架类的常量和辅助函数。

**常量：**
- `CF_SERVICE_MARKER`：`"__cf_service__"` — 在所有装饰类上设置为 `True`
- `CF_SERVICE_META`：`"__cf_service_meta__"` — 存储 `ServiceMeta`/`ModuleMeta`/`RouterMeta`
- `CF_NAME_ATTR`：`"__cf_name__"` — 自动生成的服务/模块/路由名称
- `ROUTE_ATTR`：`"__cf_route__"` — 处理器方法上的路由元数据字典
- `CF_CONFIG_MARKER`：`"__cf_config__"` — 在 `@config` 类上设置为 `True`
- `CF_HOOK_MARKER_MAP`：`LifecycleHook` 到标记字符串的映射

**函数：**
- `is_cf_service(cls)`：检查类是否具有 `CF_SERVICE_MARKER`
- `is_cf_module(cls)`：检查类是否在 `CF_SERVICE_META` 中具有 `ModuleMeta`（isinstance 检查）
- `is_cf_router(cls)`：检查类是否在 `CF_SERVICE_META` 中具有 `RouterMeta`（isinstance 检查）
- `get_service_meta(cls)`：获取服务元数据
- `get_module_meta(cls)`：获取模块元数据
- `get_router_meta(cls)`：获取路由元数据
- `resolve_deps(cls) -> dict[str, type]`：读取 `__annotations__`，返回类型具有 `CF_SERVICE_MARKER` 的条目

---

### 类型 (Types)

数据类和类型别名。

**ServiceMeta：**
```python
@dataclass(slots=True)
class ServiceMeta:
    name: str  # 自动生成："DatabaseService"
```

**ModuleMeta：**
```python
@dataclass(slots=True)
class ModuleMeta(ServiceMeta):
    services: list[type] = []  # 子服务类
```

**RouterMeta：**
```python
@dataclass(slots=True)
class RouterMeta(ServiceMeta):
    prefix: str = ""              # URL 前缀
    tags: list[str] = []          # OpenAPI 标签
    routes: list[Callable] = []   # 路由处理器方法
```

**ServiceEntry：**
```python
@dataclass(slots=True)
class ServiceEntry:
    cls: type             # 服务类
    name: str             # 自动生成的名称
    instance: object = None  # 实例（初始化前为 None）
```

**类型别名：**
- `HookFunction`：`Callable[..., object]`

---

## 引擎模块

### Registry

具有父注册表链的服务注册表。

**方法：**
- `__init__(parent: Registry = None)`：创建带有可选父注册表的注册表
- `register(cls, *, meta: ServiceMeta)`：注册服务（幂等）
- `get_by_name(name: str) -> ServiceEntry`：按名称查找
- `get_by_class(cls: type) -> ServiceEntry`：按类查找（搜索父链）
- `has(cls: type) -> bool`：检查是否已注册（搜索父链）
- `all_entries() -> list[ServiceEntry]`：获取此注册表中的所有条目
- `names() -> list[str]`：获取所有服务名称

---

### Resolver

依赖解析工具。

**函数：**
- `resolve_deps(cls) -> dict[str, type]`：读取 `cls.__annotations__` 并返回类型具有 `CF_SERVICE_MARKER` 的条目。每个键是注解属性名，用于 `setattr` 注入。
- `topological_sort(registry: Registry) -> list[str]`：使用 Kahn 算法按依赖顺序排序服务。内部使用 `resolve_deps()`。在循环依赖时抛出 `CircularDependencyError`。

---

### Hooks

生命周期钩子工具。

**HookDict：**
```python
HookDict = dict[LifecycleHook, Callable[..., object] | None]
```

**LifecycleAware 协议：**
```python
class LifecycleAware(Protocol):
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

**函数：**
- `(instance: object) -> HookDict`：遍历 MRO 查找生命周期钩子方法

---

### 路由

路由路径解析。

**函数：**
- `parse_route_path(path: str) -> tuple[str, list[str], list[str]]`：解析路由路径，返回 `(starlette_path, path_params, query_params)`。支持查询参数的 `?param={param}&param2={param2}` 语法：
  - 输入：`"/op/{kb_id}?count={count}&page={page}"`
  - 输出：`("/op/{kb_id}", ["kb_id"], ["count", "page"])`

---

## 版本

```python
__version__: str
```

Canary Framework 的当前版本。

---

## 内部属性（高级使用）

装饰类设置了以下内部属性：

- `__cf_service__`：如果使用 `@service()` 或 `@module()` 装饰则为 `True`
- `__cf_service_meta__`：元数据对象（`ServiceMeta`/`ModuleMeta`/`RouterMeta`）
- `__cf_name__`：自动生成的名称（如 `"DatabaseService"`）

钩子方法具有：
- `__cf_before_startup__`：`True`
- `__cf_before_shutdown__`：`True`

路由方法具有：
- `__cf_route__`：`{"method": "GET", "path": "/path", ...}`

配置类具有：
- `__cf_config__`：`True`

---

## 迁移说明（v1 到 v2）

与旧版 API 的主要变化：

| 旧版 API (v1) | 新版 API (v2) |
|---|---|
| `@service(name="foo")` | `@service()` — 自动命名 |
| `@service(name="foo", deps=[Bar])` | `@service()` 配合 `bar: Bar` 注解 |
| `@module(name="app", services=[...])` | `@module(services=[...])` — 自动命名 |
| `@module(name="app", deps=[...])` | 依赖通过注解声明 |
| `@router(name="api", prefix="/api", deps=[Svc])` | `@router(prefix="/api")` 配合 `svc: Svc` 注解 |
| `@router(docs=True)` | 文档默认自动启用 |
| `self.database_service`（snake_case 注入） | `self.db`、`self.cache`（注解键名） |
| `async def handler(self, request)` | `async def handler(self, ...)` — 参数自动绑定 |
| `request.path_params["user_id"]` | `def handler(self, user_id: int)` |
| `request.query_params.get("page")` | `def handler(self, page: int = 1)` |
| `data = await request.json()` | `def handler(self, body: MyModel)` 配合 `request_model` |
| `uvicorn.run("main:App")` | `uvicorn.run(app, lifespan="on")` |
| 普通 dict 传递给 `configure()` | 需要 `CanaryConfig` 子类 |
| `await app.configure(cfg)` | `await app.init()` — 单一 init 调用 |
| `make_subclass()` 工具 | 已移除 — 显式继承 |
| `CF_MODULE_MARKER` / `CF_ROUTER_MARKER` | 已移除 — 对元类型的 `isinstance` 检查 |
| `@router(prefix="/api")` 类装饰器 | `router = Router(prefix="/api")` 类属性 |
| `class X(RouterBase)` | `class X(ServiceBase)` 配合 `router` 属性 |
| `@get("/path")` | `@router.get("/path")` |
| `@post("/path")` | `@router.post("/path")` |
