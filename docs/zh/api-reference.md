# API 参考

Canary 框架的完整 API 文档。

## 主要导出

```python
from canary_framework import (
    # 装饰器
    service, module, router,
    get, post, put, delete, patch,
    after_config, after_init, before_startup, before_shutdown,

    # 基类
    RouterBase,

    # 异常
    CanaryFrameworkError,
    DependencyInjectionError,
    CircularDependencyError,
    LifecycleHookError,
    ServiceNotFoundError,
    ConfigurationError,

    # 枚举
    LifecycleHook,

    # 版本
    __version__
)
```

---

## 装饰器

### @service

将类标记为服务。**无参数调用**，服务名称自动生成为 `类名 + "Service"`。

**签名：**
```python
def service() -> Callable[[type], type[ServiceBase]]
```

**参数：** 无

**示例：**
```python
@service()
class Database:
    pass
# 服务名称自动为 "DatabaseService"
```

**行为：**
- 将类转换为 `ServiceBase` 的子类
- 添加元数据标记 `__cf_service__` 和 `__cf_service_meta__`
- 依赖通过类型注解声明（如 `db: DatabaseService`），而非 `deps` 参数
- 服务名称在模块内必须唯一

---

### @module

将类标记为模块。只需提供 `services` 参数，模块名称自动生成为 `类名 + "Module"`。

**签名：**
```python
def module(*, services: list[type] | None = None) -> Callable[[type], type[ModuleBase]]
```

**参数：**
- `services`（list[type]，可选，仅关键字）：模块直接包含的子服务类列表

**示例：**
```python
@module(services=[DatabaseService, ApiRouter])
class App:
    pass
# 模块名称自动为 "AppModule"
```

**行为：**
- 将类转换为 `ModuleBase` 的子类
- 递归注册所有子服务及其依赖（通过 `resolve_deps()` 解析）
- 构建依赖图并进行拓扑排序
- 在 `configure()` 阶段自动注入依赖
- 如果 services 中的任何类未被 `@service`/`@module` 装饰，抛出 `TypeError`

---

### @router

将类标记为路由。无 `name`/`deps` 参数，路由名称自动生成为 `类名 + "Router"`。

**签名：**
```python
def router(prefix: str = "", *, tags: list[str] | None = None) -> Callable[[type], type[RouterBase]]
```

**参数：**
- `prefix`（str，可选，位置参数）：所有路由的 URL 前缀，默认为空字符串
- `tags`（list[str]，可选，仅关键字）：用于 OpenAPI 文档的标签列表

**示例：**
```python
@router(prefix="/api", tags=["API"])
class Api:
    pass
# 路由名称自动为 "ApiRouter"
```

**行为：**
- 将类转换为 `RouterBase` 的子类
- 收集所有使用 HTTP 方法装饰器标记的方法
- 自动生成 OpenAPI 文档
- 依赖通过类型注解声明

---

### HTTP 方法装饰器

将方法标记为路由处理程序。路径参数从 URL 自动绑定，查询参数从函数签名自动识别。

**签名：**
```python
def get(path: str, *, summary=None, description=None,
        response_model=None, request_model=None,
        responses=None, tags=None, deprecated=False,
        operation_id=None) -> Callable

def post(path: str, *, ...) -> Callable
def put(path: str, *, ...) -> Callable
def delete(path: str, *, ...) -> Callable
def patch(path: str, *, ...) -> Callable
```

**参数：**
- `path`（str，必需）：路由的 URL 路径。支持 `{param}` 路径参数语法和 `?param={param}` 查询参数语法
- `summary`（str，可选）：操作的简短摘要（用于 OpenAPI）
- `description`（str，可选）：操作的详细描述（用于 OpenAPI）
- `request_model`（Pydantic BaseModel，可选）：请求体数据模型
- `response_model`（Pydantic BaseModel，可选）：响应数据模型
- `responses`（dict，可选）：自定义响应定义
- `tags`（list[str]，可选）：API 分组标签
- `deprecated`（bool，可选）：是否弃用，默认为 False
- `operation_id`（str，可选）：操作唯一标识符

**示例：**
```python
@router()
class UsersRouter:
    @get("/{user_id}", summary="获取用户", response_model=UserResponse)
    async def get_user(self, user_id: int):
        pass

    @post("/", summary="创建用户", request_model=UserCreate, response_model=UserResponse)
    async def create_user(self, user: UserCreate):
        pass
```

**响应自动转换：**
- `dict` 或 `list` → `JSONResponse`
- `Pydantic BaseModel` → `JSONResponse`（调用 `model_dump()`）
- `str` → `PlainTextResponse`
- `Response` 子类 → 直接返回

---

### 生命周期钩子装饰器

将方法标记为生命周期钩子。

**签名：**
```python
def after_config(func: HookFunction) -> HookFunction
def after_init(func: HookFunction) -> HookFunction
def before_startup(func: HookFunction) -> HookFunction
def before_shutdown(func: HookFunction) -> HookFunction
```

**钩子执行顺序：**

| 阶段 | 装饰器 | 执行时机 |
|------|--------|----------|
| 配置阶段 | `@after_config` | 服务 `configure()` 完成后 |
| 初始化阶段 | `@after_init` | 服务 `init()` 完成后 |
| 启动阶段 | `@before_startup` | 服务 `startup()` 前 |
| 关闭阶段 | `@before_shutdown` | 服务 `shutdown()` 前 |

**示例：**
```python
@service()
class Database:
    @after_config
    async def connect(self):
        pass

    @before_shutdown
    async def disconnect(self):
        pass
```

---

## 基类

### ServiceBase

服务的基类。

**属性：**
- `config`：配置对象（在配置阶段设置）
- `_cf_hooks`：内部钩子注册表

**方法：**
- `async configure(config_instance=None)`：配置服务，调用 `@after_config` 钩子
- `async init()`：初始化服务，调用 `@after_init` 钩子
- `async startup()`：启动服务，调用 `@before_startup` 钩子
- `async shutdown()`：关闭服务，调用 `@before_shutdown` 钩子（逆序）
- `async _invoke_hook(hook)`：调用指定的生命周期钩子

---

### ModuleBase

模块的基类，扩展 `ServiceBase`。

**属性：**
- `config`：配置对象
- `_cf_parent_registry`：父注册表（如果有）
- `_cf_registry`：服务注册表（`Registry` 实例）
- `_cf_startup_order`：排序后的启动顺序（`list[str]`）
- `_cf_asgi_app`：缓存的 ASGI 应用

**属性（只读）：**
- `asgi_app`：带有挂载子服务的 Starlette 路由

**方法：**
- `async configure(config_instance=None)`：配置模块和所有服务（**核心 DI 阶段**：注册、排序、实例化、注入依赖）
- `async init()`：初始化模块和所有服务
- `async startup()`：启动模块和所有服务
- `async shutdown()`：关闭模块和所有服务（逆序）
- `async __call__(scope, receive, send)`：ASGI 应用接口
- `async _handle_lifespan(receive, send)`：处理 ASGI 生命周期事件
- `_register_entry_with_deps(cls, registry)`：递归注册服务及其依赖

**子服务访问：** 配置完成后，子服务通过**原始类名**可访问：

```python
app = App()
await app.configure()

app.Database       # Database 服务实例
app.AuthService    # Auth 服务实例
```

---

### RouterBase

路由的基类，扩展 `ServiceBase`。

**属性（只读）：**
- `asgi_app`：带有收集路由的 Starlette 路由

**方法：**
- `async __call__(scope, receive, send)`：ASGI 应用接口
- `_collect_routes()`：收集所有 HTTP 路由

---

## 枚举

### LifecycleHook

生命周期钩子阶段枚举。

**值：**
- `LifecycleHook.AFTER_CONFIG`：`"after_config"` — 配置后
- `LifecycleHook.AFTER_INIT`：`"after_init"` — 初始化后
- `LifecycleHook.BEFORE_STARTUP`：`"before_startup"` — 启动前
- `LifecycleHook.BEFORE_SHUTDOWN`：`"before_shutdown"` — 关闭前

**使用示例：**
```python
from canary_framework import LifecycleHook

print(LifecycleHook.AFTER_CONFIG.value)  # "after_config"
```

---

## 异常

### CanaryFrameworkError

所有框架错误的基异常。

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

**触发场景：**
- 依赖服务未注册
- 配置过程中服务实例为 None

---

### CircularDependencyError

检测到循环依赖。

**触发场景：**
- 服务 A 依赖服务 B，服务 B 又依赖服务 A
- 更长的循环依赖链

---

### LifecycleHookError

生命周期钩子执行期间发生错误。

**触发场景：**
- 钩子函数抛出异常
- 钩子函数签名不正确

---

### ServiceNotFoundError

注册表中未找到服务。

**触发场景：**
- 尝试获取未注册的服务
- 依赖的服务未在模块中注册

---

### ConfigurationError

配置错误。

**触发场景：**
- 配置类缺失必需属性
- 配置值无效

---

## 通用模块

### 标记 (markers)

用于标识框架类的常量和辅助函数。

**常量：**
- `CF_SERVICE_MARKER = "__cf_service__"`
- `CF_MODULE_MARKER = "__cf_module__"`
- `CF_ROUTER_MARKER = "__cf_router__"`
- `CF_NAME_ATTR = "__cf_name__"`
- `CF_SERVICE_META = "__cf_service_meta__"`
- `ROUTE_ATTR = "__cf_route__"`
- `CF_HOOK_MARKER_MAP`：`LifecycleHook` 到标记字符串的映射

**函数：**
- `is_cf_service(cls)`：检查类是否为服务
- `is_cf_module(cls)`：检查类是否为模块
- `is_cf_router(cls)`：检查类是否为路由
- `get_service_meta(cls)`：获取服务元数据（返回 `ServiceMeta`）
- `get_module_meta(cls)`：获取模块元数据（返回 `ModuleMeta`）
- `get_router_meta(cls)`：获取路由元数据（返回 `RouterMeta | None`）
- `resolve_deps(cls)`：从类型注解解析依赖映射（返回 `dict[str, type]`）

---

### 类型 (types)

数据类和类型别名。

**ServiceMeta：**
```python
@dataclass(slots=True)
class ServiceMeta:
    name: str
```

**ModuleMeta：**
```python
@dataclass(slots=True)
class ModuleMeta(ServiceMeta):
    services: list[type] = field(default_factory=list)
```

**RouterMeta：**
```python
@dataclass(slots=True)
class RouterMeta(ServiceMeta):
    prefix: str = ""
    tags: list[str] = field(default_factory=list)
    routes: list[HookFunction] = field(default_factory=list)
```

**ServiceEntry：**
```python
@dataclass(slots=True)
class ServiceEntry:
    cls: type
    name: str
    instance: object | None = field(default=None)
```

**类型别名：**
- `HookFunction`：`Callable[..., object]`

---

## 引擎模块

### Registry

服务注册表类。

**方法：**
- `__init__(parent: Registry = None)`：创建带有可选父注册表的注册表
- `register(cls, *, meta)`：注册服务类（幂等操作）
- `get_by_name(name)`：按名称获取服务条目（返回 `ServiceEntry`）
- `get_by_class(cls)`：按类获取服务条目（会查找父注册表，返回 `ServiceEntry`）
- `has(cls)`：检查服务是否已注册（会查找父注册表，返回 `bool`）
- `all_entries()`：获取所有服务条目（返回 `list[ServiceEntry]`）
- `names()`：获取所有服务名称（返回 `list[str]`）

**特殊方法：**
- `__contains__(cls)`：检查服务是否注册

---

### Injector

依赖注入工具。

**函数：**
- `topological_sort(registry: Registry) -> list[str]`：按依赖顺序排序服务（使用 `resolve_deps()` 构建依赖图，Kahn 算法）

**拓扑排序说明：**
- 通过 `resolve_deps()` 读取每个注册类的类型注解来构建依赖图
- 确保依赖服务在其依赖者之前启动
- 如果检测到循环依赖，抛出 `CircularDependencyError`

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
    async def configure(self, config_instance=None) -> None: ...
    async def init(self) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

**函数：**
- `find_hooks(instance: object) -> HookDict`：查找实例上的所有生命周期钩子

---

### Utils

实用函数。

**函数：**
- `make_subclass(cls: type, base: type, meta: ServiceMeta, name: str, *, extra_marker=None) -> type`：创建带有框架元数据的子类

---

### OpenAPI

OpenAPI 文档生成工具。

**函数：**
- `generate_openapi_schema(routers: list[RouterMeta]) -> dict`：生成 OpenAPI Schema

**自动生成的端点：**
- `/docs`：Swagger UI
- `/redoc`：ReDoc
- `/openapi.json`：OpenAPI JSON Schema

---

### Routing

路由路径解析工具。

**函数：**
- `parse_route_path(path: str) -> tuple[str, list[str], list[str]]`：解析路由路径，返回 `(starlette_path, path_params, query_params)`

---

## 版本

```python
__version__: str
```

Canary 框架的当前版本。

```python
from canary_framework import __version__
print(f"Canary Framework v{__version__}")
```

---

## 内部属性（高级使用）

装饰类设置了这些内部属性：

- `__cf_service__`：如果用 `@service` 装饰则为 `True`
- `__cf_module__`：如果用 `@module` 装饰则为 `True`
- `__cf_router__`：如果用 `@router` 装饰则为 `True`
- `__cf_service_meta__`：元数据对象（`ServiceMeta`/`ModuleMeta`/`RouterMeta`）
- `__cf_name__`：服务/模块/路由名称

钩子方法有：
- `__cf_after_config__`：`True`
- `__cf_after_init__`：`True`
- `__cf_before_startup__`：`True`
- `__cf_before_shutdown__`：`True`

路由方法有：
- `__cf_route__`：`{"method": "GET", "path": "/path", "summary": "...", ...}`

---

## 配置类约定

配置类应遵循以下约定：

```python
class AppConfig:
    def __init__(self):
        self.database_url = "sqlite:///app.db"
        self.debug = True
        self.port = 8000
```

配置类的属性会在 `configure` 阶段注入到所有服务的 `config` 属性中。

框架日志级别可通过 `cf_log_level` 字段配置：

```python
class AppConfig:
    cf_log_level: str = "DEBUG"  # 默认 "INFO"
```

---

## 最佳实践

1. **依赖声明**：通过类型注解声明依赖，而非旧的 `deps` 参数
2. **依赖最小化**：只声明真正需要的依赖
3. **类型提示**：使用类型提示提高代码质量和 IDE 支持
4. **错误处理**：在生命周期钩子中妥善处理异常
5. **模块组织**：按功能划分模块，提高可维护性
6. **简洁命名**：类名简短，框架自动追加类型后缀
