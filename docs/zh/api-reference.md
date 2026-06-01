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

---

### @module

将类标记为模块。

**签名：**
```python
def module(
    name: str,
    *,
    deps: List[type] = None,
    services: List[type] = None
) -> Callable[[type], type[ModuleBase]]
```

**参数：**
- `name`（str，必需）：模块的唯一标识符
- `deps`（List[type]，可选）：模块的依赖项
- `services`（List[type]，可选）：模块包含的服务/模块
- `config`（type，可选）：模块的配置类

**示例：**
```python
@module(name="app", services=[DatabaseService, ApiRouter])
class AppModule:
    pass
```

---

### @router

将类标记为路由。

**签名：**
```python
def router(
    name: str,
    prefix: str = "",
    *,
    deps: List[type] = None,
    tags: List[str] = None
) -> Callable[[type], type[RouterBase]]
```

**参数：**
- `name`（str，必需）：路由的唯一标识符
- `prefix`（str，可选）：所有路由的 URL 前缀
- `deps`（List[type]，可选）：路由的依赖项
- `tags`（List[str]，可选）：文档的 OpenAPI 标签

**示例：**
```python
@router(name="api", prefix="/api", deps=[UserService])
class ApiRouter:
    pass
```

---

### HTTP 方法装饰器

将方法标记为路由处理程序。

**签名：**
```python
def get(path: str) -> Callable[[HookFunction], HookFunction]
def post(path: str) -> Callable[[HookFunction], HookFunction]
def put(path: str) -> Callable[[HookFunction], HookFunction]
def delete(path: str) -> Callable[[HookFunction], HookFunction]
def patch(path: str) -> Callable[[HookFunction], HookFunction]
```

**参数：**
- `path`（str，必需）：路由的 URL 路径

**示例：**
```python
@router(name="users")
class UsersRouter:
    @get("/{user_id}")
    async def get_user(self, request):
        pass
    
    @post("/")
    async def create_user(self, request):
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
- `_cf_hooks`：内部钩子注册表

**方法：**
- `async configure(config_instance=None)`：配置服务
- `async init()`：初始化服务
- `async startup()`：启动服务
- `async shutdown()`：关闭服务
- `async _invoke_hook(hook)`：调用生命周期钩子

---

### ModuleBase

模块的基类，扩展 ServiceBase。

**属性：**
- `config`：配置对象
- `_cf_parent_registry`：父注册表（如果有）
- `_cf_registry`：服务注册表
- `_cf_startup_order`：排序的启动顺序
- `_cf_asgi_app`：缓存的 ASGI 应用

**属性：**
- `asgi_app`：带有挂载子服务的 Starlette 路由

**方法：**
- `async configure(config_instance=None)`：配置模块和所有服务
- `async init()`：初始化模块和所有服务
- `async startup()`：启动模块和所有服务
- `async shutdown()`：关闭模块和所有服务
- `async __call__(scope, receive, send)`：ASGI 应用接口
- `async _handle_lifespan(receive, send)`：处理 ASGI 生命周期事件
- `_register_entry_with_deps(cls, registry)`：递归注册服务

---

### RouterBase

路由的基类，扩展 ServiceBase。

**属性：**
- `asgi_app`：带有收集路由的 Starlette 路由

**方法：**
- `async __call__(scope, receive, send)`：ASGI 应用接口

---

## 枚举

### LifecycleHook

生命周期钩子阶段。

**值：**
- `LifecycleHook.AFTER_CONFIG`："after_config"
- `LifecycleHook.AFTER_INIT`："after_init"
- `LifecycleHook.BEFORE_STARTUP`："before_startup"
- `LifecycleHook.BEFORE_SHUTDOWN`："before_shutdown"

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

依赖注入期间错误。

---

### CircularDependencyError

检测到循环依赖。

---

### LifecycleHookError

生命周期钩子中的错误。

---

### ServiceNotFoundError

注册表中未找到服务。

---

### ConfigurationError

配置错误。

---

## 通用模块

### 标记

用于标识框架类的常量和辅助函数。

**常量：**
- `CF_SERVICE_MARKER`："__cf_service__"
- `CF_MODULE_MARKER`："__cf_module__"
- `CF_ROUTER_MARKER`："__cf_router__"
- `CF_NAME_ATTR`："__cf_name__"
- `ROUTE_ATTR`："__cf_route__"
- `CF_HOOK_MARKER_MAP`：LifecycleHook 到标记字符串的映射

**函数：**
- `is_cf_service(cls)`：检查类是否为服务
- `is_cf_module(cls)`：检查类是否为模块
- `is_cf_router(cls)`：检查类是否为路由
- `get_service_meta(cls)`：获取服务元数据
- `get_module_meta(cls)`：获取模块元数据

---

### 类型

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
    routes: List[HookFunction] = field(default_factory=list)
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
- `HookFunction`：Callable[..., object]

---

## 引擎模块

### Registry

服务注册表类。

**方法：**
- `__init__(parent: Registry = None)`：创建带有可选父注册表的注册表
- `register(cls, *, meta=None)`：注册服务
- `get_by_name(name)`：按名称获取服务条目
- `get_by_class(cls)`：按类获取服务条目
- `get_instance(cls)`：按类获取服务实例
- `has(cls)`：检查服务是否注册
- `all_entries()`：获取所有服务条目
- `names()`：获取所有服务名称

**特殊方法：**
- `__len__()`：服务数量
- `__contains__(cls)`：检查服务是否注册
- `__iter__()`：迭代服务条目

---

### Injector

依赖注入工具。

**函数：**
- `to_snake(name)`：将 camelCase 转换为 snake_case
- `topological_sort(registry)`：按依赖顺序排序服务
- `inject_deps(instance, entry, registry)`：将依赖注入实例

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
- `find_hooks(instance)`：查找实例上的所有生命周期钩子

---

### Utils

实用函数。

**函数：**
- `make_subclass(cls, base_class, meta, name, extra_marker=None)`：创建带有框架元数据的子类

---

## 版本

```python
__version__: str
```

Canary 框架的当前版本。

---

## 内部属性（高级使用）

装饰类设置了这些内部属性：

- `__cf_service__`：如果用 @service 装饰则为 `True`
- `__cf_module__`：如果用 @module 装饰则为 `True`
- `__cf_router__`：如果用 @router 装饰则为 `True`
- `__cf_service_meta__`：元数据对象（ServiceMeta/ModuleMeta/RouterMeta）
- `__cf_name__`：服务/模块名称

钩子方法有：
- `__cf_after_config__`：`True`
- `__cf_after_init__`：`True`
- `__cf_before_startup__`：`True`
- `__cf_before_shutdown__`：`True`

路由方法有：
- `__cf_route__`：`{"method": "GET", "path": "/path"}`
