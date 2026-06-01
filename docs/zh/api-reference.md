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
    ServiceBase, ModuleBase, RouterBase,
    
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

将类标记为服务。

**签名：**
```python
def service(name: str, *, deps: List[type] = None) -> Callable[[type], type[ServiceBase]]
```

**参数：**
- `name`（str，必需）：服务的唯一标识符
- `deps`（List[type]，可选）：此服务依赖的服务类列表

**示例：**
```python
@service(name="database", deps=[ConfigService])
class DatabaseService:
    pass
```

**行为：**
- 将类转换为 `ServiceBase` 的子类
- 添加元数据标记 `__cf_service__` 和 `__cf_service_meta__`
- 服务名称在模块内必须唯一

---

### @module

将类标记为模块。

**签名：**
```python
def module(
    name: str,
    *,
    deps: List[type] = None,
    services: List[type] = None,
    config: type = None
) -> Callable[[type], type[ModuleBase]]
```

**参数：**
- `name`（str，必需）：模块的唯一标识符
- `deps`（List[type]，可选）：模块的依赖项
- `services`（List[type]，可选）：模块包含的服务/模块列表
- `config`（type，可选）：模块的配置类

**示例：**
```python
@module(name="app", services=[DatabaseService, ApiRouter], config=AppConfig)
class AppModule:
    pass
```

**行为：**
- 将类转换为 `ModuleBase` 的子类
- 递归注册所有子服务
- 构建依赖图并进行拓扑排序

---

### @router

将类标记为路由。

**签名：**
```python
def router(
    name: str,
    *,
    prefix: str = "",
    deps: List[type] = None,
    tags: List[str] = None
) -> Callable[[type], type[RouterBase]]
```

**参数：**
- `name`（str，必需）：路由的唯一标识符
- `prefix`（str，可选）：所有路由的 URL 前缀，默认为空字符串
- `deps`（List[type]，可选）：路由依赖的服务类列表
- `tags`（List[str]，可选）：用于 OpenAPI 文档的标签列表

**示例：**
```python
@router(name="api", prefix="/api", deps=[UserService], tags=["API"])
class ApiRouter:
    pass
```

**行为：**
- 将类转换为 `RouterBase` 的子类
- 收集所有使用 HTTP 方法装饰器标记的方法
- 自动生成 OpenAPI 文档

---

### HTTP 方法装饰器

将方法标记为路由处理程序。

**签名：**
```python
def get(path: str, *, summary=None, description=None, 
        request_model=None, response_model=None,
        responses=None, tags=None, deprecated=False,
        operation_id=None, path_params=None, query_params=None) -> Callable

def post(path: str, *, ...) -> Callable
def put(path: str, *, ...) -> Callable
def delete(path: str, *, ...) -> Callable
def patch(path: str, *, ...) -> Callable
```

**参数：**
- `path`（str，必需）：路由的 URL 路径
- `summary`（str，可选）：操作的简短摘要（用于 OpenAPI）
- `description`（str，可选）：操作的详细描述（用于 OpenAPI）
- `request_model`（Pydantic BaseModel，可选）：请求体数据模型
- `response_model`（Pydantic BaseModel，可选）：响应数据模型
- `responses`（dict，可选）：自定义响应定义
- `tags`（List[str]，可选）：API 分组标签
- `deprecated`（bool，可选）：是否弃用，默认为 False
- `operation_id`（str，可选）：操作唯一标识符
- `path_params`（dict，可选）：路径参数定义
- `query_params`（dict，可选）：查询参数定义

**示例：**
```python
@router(name="users")
class UsersRouter:
    @get("/{user_id}", summary="获取用户", response_model=UserResponse)
    async def get_user(self, request):
        pass
    
    @post("/", summary="创建用户", request_model=UserCreate, response_model=UserResponse)
    async def create_user(self, request, user: UserCreate):
        pass
```

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
| 配置阶段 | `@after_config` | 服务配置完成后 |
| 初始化阶段 | `@after_init` | 服务初始化完成后 |
| 启动阶段 | `@before_startup` | 服务启动前 |
| 关闭阶段 | `@before_shutdown` | 服务关闭前 |

**示例：**
```python
@service(name="database")
class DatabaseService:
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
- `_cf_hooks`：内部钩子注册表（`Dict[LifecycleHook, List[Callable]]`）
- `_cf_service_meta`：服务元数据对象

**方法：**
- `async configure(config_instance=None)`：配置服务，调用 `@after_config` 钩子
- `async init()`：初始化服务，调用 `@after_init` 钩子
- `async startup()`：启动服务，调用 `@before_startup` 钩子
- `async shutdown()`：关闭服务，调用 `@before_shutdown` 钩子（逆序）
- `async _invoke_hook(hook)`：调用指定的生命周期钩子

---

### ModuleBase

模块的基类，扩展 ServiceBase。

**属性：**
- `config`：配置对象
- `_cf_parent_registry`：父注册表（如果有）
- `_cf_registry`：服务注册表（`Registry` 实例）
- `_cf_startup_order`：排序后的启动顺序（`List[type]`）
- `_cf_asgi_app`：缓存的 ASGI 应用

**属性（只读）：**
- `asgi_app`：带有挂载子服务的 Starlette 路由

**方法：**
- `async configure(config_instance=None)`：配置模块和所有服务
- `async init()`：初始化模块和所有服务
- `async startup()`：启动模块和所有服务
- `async shutdown()`：关闭模块和所有服务（逆序）
- `async __call__(scope, receive, send)`：ASGI 应用接口
- `async _handle_lifespan(receive, send)`：处理 ASGI 生命周期事件
- `_register_entry_with_deps(cls, registry)`：递归注册服务及其依赖

---

### RouterBase

路由的基类，扩展 ServiceBase。

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
- `LifecycleHook.AFTER_CONFIG`："after_config" - 配置后
- `LifecycleHook.AFTER_INIT`："after_init" - 初始化后
- `LifecycleHook.BEFORE_STARTUP`："before_startup" - 启动前
- `LifecycleHook.BEFORE_SHUTDOWN`："before_shutdown" - 关闭前

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
- 依赖注入失败

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
- `CF_SERVICE_MARKER`："__cf_service__"
- `CF_MODULE_MARKER`："__cf_module__"
- `CF_ROUTER_MARKER`："__cf_router__"
- `CF_NAME_ATTR`："__cf_name__"
- `ROUTE_ATTR`："__cf_route__"
- `CF_HOOK_MARKER_MAP`：`LifecycleHook` 到标记字符串的映射

**函数：**
- `is_cf_service(cls)`：检查类是否为服务
- `is_cf_module(cls)`：检查类是否为模块
- `is_cf_router(cls)`：检查类是否为路由
- `get_service_meta(cls)`：获取服务元数据（返回 `ServiceMeta`）
- `get_module_meta(cls)`：获取模块元数据（返回 `ModuleMeta`）
- `get_router_meta(cls)`：获取路由元数据（返回 `RouterMeta`）

---

### 类型 (types)

数据类和类型别名。

**ServiceMeta：**
```python
@dataclass
class ServiceMeta:
    name: str
    deps: List[type] = field(default_factory=list)
```

**ModuleMeta：**
```python
@dataclass
class ModuleMeta(ServiceMeta):
    services: List[type] = field(default_factory=list)
    config_cls: type = None
```

**RouterMeta：**
```python
@dataclass
class RouterMeta(ServiceMeta):
    prefix: str = ""
    tags: List[str] = field(default_factory=list)
    routes: List[dict] = field(default_factory=list)
```

**ServiceEntry：**
```python
@dataclass
class ServiceEntry:
    cls: type
    name: str
    instance: object = None
    deps: List[type] = field(default_factory=list)
    dep_names: List[str] = field(default_factory=list)
```

**类型别名：**
- `HookFunction`：`Callable[..., Awaitable[object] | object]`
- `RouteFunction`：`Callable[[Any, Request], Awaitable[Response] | dict | str | int]`

---

## 引擎模块

### Registry

服务注册表类。

**方法：**
- `__init__(parent: Registry = None)`：创建带有可选父注册表的注册表
- `register(cls, *, meta=None)`：注册服务类
- `get_by_name(name)`：按名称获取服务条目（返回 `ServiceEntry`）
- `get_by_class(cls)`：按类获取服务条目（返回 `ServiceEntry`）
- `get_instance(cls)`：按类获取服务实例（返回对象或 None）
- `has(cls)`：检查服务是否已注册（返回 bool）
- `all_entries()`：获取所有服务条目（返回 `List[ServiceEntry]`）
- `names()`：获取所有服务名称（返回 `List[str]`）

**特殊方法：**
- `__len__()`：返回服务数量
- `__contains__(cls)`：检查服务是否注册
- `__iter__()`：迭代服务条目

---

### Injector

依赖注入工具。

**函数：**
- `to_snake(name: str) -> str`：将 PascalCase/camelCase 转换为 snake_case
- `topological_sort(registry: Registry) -> List[type]`：按依赖顺序排序服务（使用 Kahn 算法）
- `inject_deps(instance: object, entry: ServiceEntry, registry: Registry) -> None`：将依赖注入到实例

**拓扑排序说明：**
- 使用 Kahn 算法进行拓扑排序
- 确保依赖服务在其依赖者之前启动
- 如果检测到循环依赖，抛出 `CircularDependencyError`

---

### Hooks

生命周期钩子工具。

**HookDict：**
```python
HookDict = Dict[LifecycleHook, Optional[List[Callable]]]
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
- `invoke_hook(instance: object, hook: LifecycleHook) -> Awaitable[None]`：调用指定的钩子

---

### Utils

实用函数。

**函数：**
- `make_subclass(cls: type, base_class: type, meta: object, name: str, extra_marker=None) -> type`：创建带有框架元数据的子类
- `merge_tags(router_tags: List[str], method_tags: List[str]) -> List[str]`：合并路由级别和方法级别的标签

---

### OpenAPI

OpenAPI 文档生成工具。

**函数：**
- `generate_openapi_schema(routers: List[RouterBase]) -> dict`：生成 OpenAPI Schema
- `get_openapi_json(app: ModuleBase) -> str`：获取 OpenAPI JSON 字符串

**自动生成的端点：**
- `/docs`：Swagger UI
- `/redoc`：ReDoc
- `/openapi.json`：OpenAPI JSON Schema

---

## 版本

```python
__version__: str
```

Canary 框架的当前版本。

**示例：**
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
- `__cf_name__`：服务/模块名称

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

---

## 最佳实践

1. **服务命名**：使用描述性名称，避免歧义
2. **依赖最小化**：只声明真正需要的依赖
3. **类型提示**：使用类型提示提高代码质量
4. **错误处理**：在生命周期钩子中妥善处理异常
5. **模块组织**：按功能划分模块，提高可维护性