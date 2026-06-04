# API 参考

Canary Framework 的完整 API 文档。

## 主要导出

```python
from canary_framework import (
    # 装饰器
    config, service, module, router,
    get, post, put, delete, patch,
    after_config, after_init, before_startup, before_shutdown,

    # 配置
    CanaryConfig,

    # 基类
    ServiceBase, ModuleBase, RouterBase,

    # 异常
    CanaryFrameworkError,
    DependencyInjectionError,
    CircularDependencyError,
    LifecycleHookError,
    ServiceNotFoundError,

    # 枚举
    LifecycleHook,

    # 版本
    __version__
)
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
    services: List[type] = None
) -> Callable[[type], type[ModuleBase]]
```

**参数：**
- `services`（List[type]，仅关键字）：此模块包含的服务、路由和子模块

`name` 和 `deps` 参数已移除。模块名称自动生成为 `ClassName` + `"Module"`。

**示例：**
```python
@module(services=[Database, Auth, Api])
class App(ModuleBase):
    pass
```

---

### @router

将类标记为路由。

**签名：**
```python
def router(
    prefix: str = "",
    *,
    tags: List[str] = None
) -> Callable[[type], type[RouterBase]]
```

**参数：**
- `prefix`（str，位置参数，默认 `""`）：所有路由的 URL 前缀
- `tags`（List[str]，仅关键字）：用于文档的 OpenAPI 标签

`name` 和 `deps` 参数已移除。路由名称自动生成为 `ClassName` + `"Router"`。依赖通过类型注解声明。

**示例：**
```python
@router(prefix="/api", tags=["API"])
class Api(RouterBase):
    pass
```

---

### HTTP 方法装饰器

将方法标记为路由处理器。

**签名：**
```python
def get(path: str, **kwargs) -> Callable
def post(path: str, **kwargs) -> Callable
def put(path: str, **kwargs) -> Callable
def delete(path: str, **kwargs) -> Callable
def patch(path: str, **kwargs) -> Callable
```

**参数：**
- `path`（str，必需）：路由的 URL 路径
- `summary`（str）：OpenAPI 简短摘要
- `description`（str）：OpenAPI 详细描述
- `request_model`（Pydantic BaseModel）：将请求体自动解析为此模型。作为 `body` 参数传入。
- `response_model`（Pydantic BaseModel）：OpenAPI 响应数据模型
- `responses`（dict）：自定义响应定义
- `tags`（list[str]）：OpenAPI 标签
- `deprecated`（bool）：标记为已弃用
- `operation_id`（str）：唯一操作标识符
- `path_params`（dict）：路径参数定义，用于 schema 补充
- `query_params`（dict）：查询参数定义，用于 schema 补充

路由处理器**不**接收 `request` 参数。路径参数、查询参数和请求体自动绑定。

**示例：**
```python
@router(prefix="/users")
class Users(RouterBase):
    @get("/{user_id}")
    async def get_user(self, user_id: int):
        # user_id 从 URL 路径自动绑定
        pass

    @post("/", request_model=UserCreate)
    async def create_user(self, body: UserCreate):
        # body 从请求体自动解析
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

配置类必须继承 `CanaryConfig`。

**示例：**
```python
from canary_framework import config
from canary_framework.common.config import CanaryConfig

@config
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
def after_config(func) -> HookFunction
def after_init(func) -> HookFunction
def before_startup(func) -> HookFunction
def before_shutdown(func) -> HookFunction
```

**示例：**
```python
@service()
class Database(ServiceBase):
    @after_config
    async def connect(self):
        pass

    @before_shutdown
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
| `openapi_title` | `str` | `"Canary Framework API"` | API 标题 |
| `openapi_version` | `str` | `"1.0.0"` | API 版本 |
| `openapi_description` | `str` | `""` | API 描述 |
| `openapi_servers` | `list[dict]` | `[]` | OpenAPI 服务器列表 |
| `openapi_security_schemes` | `dict` | `{}` | 安全方案 |
| `docs_openapi_path` | `str` | `"/openapi.json"` | OpenAPI JSON 路径 |
| `docs_swagger_path` | `str` | `"/docs"` | Swagger UI 路径 |
| `docs_redoc_path` | `str` | `"/redoc"` | ReDoc 路径 |
| `docs_swagger_css_cdn` | `str` | Swagger CSS CDN | CSS CDN URL |
| `docs_swagger_js_cdn` | `str` | Swagger JS CDN | JS CDN URL |
| `docs_redoc_cdn` | `str` | ReDoc JS CDN | ReDoc CDN URL |

允许额外字段 — 您可以添加任意自定义配置字段。

### ServiceBase

服务的基类。

**属性：**
- `config`：配置对象（在配置阶段设置）
- `_cf_hooks`：内部钩子注册表
- `_cf_parent_registry`：父注册表引用

**方法：**
- `async configure(config_instance: CanaryConfig | None = None)`：配置服务
- `async init()`：初始化服务
- `async startup()`：启动服务
- `async shutdown()`：关闭服务
- `async __call__(scope, receive, send)`：ASGI 应用接口（处理 lifespan 事件）
- `async _handle_lifespan(receive, send)`：处理 ASGI lifespan 事件
- `async _invoke_hook(hook)`：调用生命周期钩子

---

### ModuleBase

模块的基类，扩展 ServiceBase。

**属性：**
- `config`：配置对象
- `_cf_parent_registry`：父注册表（如果有）
- `_cf_registry`：服务注册表
- `_cf_startup_order`：排序后的启动顺序
- `_cf_asgi_app`：缓存的 ASGI 应用

**属性（只读）：**
- `asgi_app`：带有挂载子服务的 Starlette 路由

**方法：**
- `async configure(config_instance: CanaryConfig | None = None)`：配置模块和所有服务
- `async init()`：初始化模块和所有服务
- `async startup()`：启动模块和所有服务
- `async shutdown()`：关闭模块和所有服务
- `_register_entry_with_deps(cls, registry)`：递归注册服务及其通过注解解析的依赖

---

### RouterBase

路由的基类，扩展 ServiceBase。

**属性（只读）：**
- `asgi_app`：带有收集路由的 Starlette 路由

**方法：**
- `async configure(config_instance: CanaryConfig | None = None)`：配置路由
- `async startup()`：启动路由（自动注册 OpenAPI 文档）
- `get_mount_path()`：获取此路由的挂载路径
- `_cf_get_root_routes()`：获取 ASGI 应用的根路由

---

## 枚举

### LifecycleHook

生命周期钩子阶段。

**值：**
- `LifecycleHook.AFTER_CONFIG`：`"after_config"`
- `LifecycleHook.AFTER_INIT`：`"after_init"`
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
    ├── DependencyInjectionError
    ├── CircularDependencyError
    ├── LifecycleHookError
    ├── ConfigurationError
    └── ServiceNotFoundError
```

---

### DependencyInjectionError

依赖注入期间发生错误。

---

### CircularDependencyError

检测到循环依赖。

---

### LifecycleHookError

生命周期钩子中发生错误。

---

### ServiceNotFoundError

注册表中未找到服务。

---

### ConfigurationError

配置错误。

---

## 通用模块

### 标记 (Markers)

用于标识框架类的常量和辅助函数。

**常量：**
- `CF_SERVICE_MARKER`：`"__cf_service__"`
- `CF_NAME_ATTR`：`"__cf_name__"`
- `ROUTE_ATTR`：`"__cf_route__"`
- `CF_HOOK_MARKER_MAP`：LifecycleHook 到标记字符串的映射

**函数：**
- `is_cf_service(cls)`：检查类是否为服务
- `is_cf_module(cls)`：检查类是否为模块
- `is_cf_router(cls)`：检查类是否为路由
- `get_service_meta(cls)`：获取服务元数据
- `get_module_meta(cls)`：获取模块元数据

---

### 类型 (Types)

数据类和类型别名。

**ServiceMeta：**
```python
@dataclass
class ServiceMeta:
    name: str                       # 自动生成的服务名称（如 "DatabaseService"）
```

**ModuleMeta：**
```python
@dataclass
class ModuleMeta(ServiceMeta):
    services: List[type] = []       # 子服务/模块
```

**RouterMeta：**
```python
@dataclass
class RouterMeta(ServiceMeta):
    prefix: str = ""                # URL 前缀
    tags: List[str] = []            # OpenAPI 标签
    routes: List[Callable] = []     # 路由处理器方法
```

**ServiceEntry：**
```python
@dataclass
class ServiceEntry:
    cls: type                       # 服务类
    name: str                       # 自动生成的名称
    instance: object = None         # 服务实例（配置前为 None）
```

**类型别名：**
- `HookFunction`：`Callable[..., object]`

---

## 引擎模块

### Registry

服务注册表类。

**方法：**
- `__init__(parent: Registry = None)`：创建带有可选父注册表的注册表
- `register(cls, *, meta=None)`：注册服务
- `get_by_name(name)`：按名称获取服务条目
- `get_by_class(cls)`：按类获取服务条目
- `has(cls)`：检查服务是否已注册
- `all_entries()`：获取所有服务条目
- `names()`：获取所有服务名称

---

### Resolver

依赖解析工具。

**函数：**
- `resolve_deps(cls) -> Dict[str, type]`：读取类的 `__annotations__` 并返回类型标记了 `CF_SERVICE_MARKER` 的条目。这替代了旧的 `deps` 列表。每个返回的键是注解属性名，将用于 `setattr` 注入。
- `topological_sort(registry) -> List[ServiceEntry]`：使用 Kahn 算法按依赖顺序排序服务。内部使用 `resolve_deps()` 构建依赖图。

---

### Hooks

生命周期钩子工具。

**HookDict：**
```python
HookDict = Dict[LifecycleHook, Optional[Callable[..., object]]]
```

**LifecycleAware 协议：**
```python
class LifecycleAware(Protocol):
    async def configure(self, config_instance=None) -> None: ...
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

**函数：**
- `find_hooks(instance)`：在实例上查找所有生命周期钩子

---

### Utils

工具函数。

---

## 版本

```python
__version__: str
```

Canary Framework 的当前版本。

---

## 内部属性（高级使用）

装饰类设置了以下内部属性：

- `__cf_service__`：如果使用 `@service()` 装饰则为 `True`
- `__cf_service_meta__`：元数据对象（ServiceMeta/ModuleMeta/RouterMeta）
- `__cf_name__`：自动生成的服务/模块/路由名称

钩子方法具有：
- `__cf_after_config__`：`True`
- `__cf_after_init__`：`True`
- `__cf_before_startup__`：`True`
- `__cf_before_shutdown__`：`True`

路由方法具有：
- `__cf_route__`：`{"method": "GET", "path": "/path", ...}`

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
| `self.database_service`（snake_case 注入） | `self.db`、`self.cache`（注解键名） |
| `async def handler(self, request)` | `async def handler(self, ...)` — 参数自动绑定 |
| `request.path_params["user_id"]` | `def handler(self, user_id: int)` |
| `request.query_params.get("page")` | `def handler(self, page: int = 1)` |
| `data = await request.json()` | `def handler(self, body: MyModel)` 配合 `request_model` |
| `app.auth_module` / `app.auth_service` | `app.AuthModule` / `app.AuthService`（类名访问） |
| `inject_deps(instance, entry, registry)` | `setattr(instance, key, resolved)` 通过注解键 |
