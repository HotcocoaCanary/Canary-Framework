# API 参考

## 装饰器

### `@service(name, *, deps=None)`

将类声明为 CF 框架的服务（最小运行单元）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称，用于依赖声明和名称索引 |
| `deps` | `list[type] \| None` | | 依赖的服务类列表，自动注入为 snake_case 属性 |

### `@module(name, *, services=None)`

将类声明为 CF 框架的模块（服务的组合容器）。`@module` 内部调用 `@service` —— 模块也是服务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称 |
| `services` | `list[type] \| None` | | 子服务和子模块类列表 |

### `@router(prefix, *, name=None, deps=None, tags=None)`

将类声明为路由。`@router` 内部调用 `@service` —— 路由也是服务。由 `WebCanary` 自动发现。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prefix` | `str` | ✓ | 应用于该组所有路由的 URL 前缀 |
| `name` | `str` | | 服务名称（省略时通过 `to_snake` 自动生成） |
| `deps` | `list[type] \| None` | | 通过 DI 注入的依赖列表 |
| `tags` | `list[str] \| None` | | 应用于所有路由的 OpenAPI 标签 |

### HTTP 方法装饰器

| 装饰器 | 签名 | HTTP 方法 |
|--------|------|-----------|
| `@get(path, **kwargs)` | `(path, *, response_model=None, status_code=None, ...)` | GET |
| `@post(path, **kwargs)` | 同上 | POST |
| `@put(path, **kwargs)` | 同上 | PUT |
| `@delete(path, **kwargs)` | 同上 | DELETE |
| `@patch(path, **kwargs)` | 同上 | PATCH |

关键字参数直接传递到 FastAPI 的 `app.add_api_route()`。

### 生命周期钩子

| 装饰器 | 签名 | 执行顺序 | 说明 |
|--------|------|----------|------|
| `@on_config` | `()` | 拓扑序 | wiring 之后、on_init 之前执行，config 属性在此可用 |
| `@on_init` | `()` | 拓扑序 | 依赖已注入、配置已加载，无需 `ctx` 参数 |
| `@on_start` | `()` | 拓扑序 | 无参数 |
| `@on_end` | `()` | 逆序 | 无参数 |

钩子方法可以是 `sync` 或 `async`，框架通过 `asyncio.iscoroutine` 自动适配。

### `LifecycleHook` 枚举

```python
from canary_framework import LifecycleHook

LifecycleHook.CONFIG # "on_config"
LifecycleHook.INIT   # "on_init"
LifecycleHook.START  # "on_start"
LifecycleHook.END    # "on_end"
```

---

## 类型系统

### 元数据类型

框架将元数据以 dataclass 存储于 `__cf_service_meta__`：

```python
@dataclass
class ServiceMeta:
    name: str
    deps: list[type]

@dataclass
class ModuleMeta(ServiceMeta):
    services: list[type]

@dataclass
class RouterMeta(ServiceMeta):
    prefix: str
    tags: list[str]
```

`isinstance(meta, RouterMeta)` / `isinstance(meta, ModuleMeta)` 用于区分不同元数据类型。

### `ServiceEntry`

```python
@dataclass
class ServiceEntry:
    cls: type
    meta: ServiceMeta
    instance: Any | None
    parent_entry: ServiceEntry | None
```

---

## 引擎类

### `Canary(target: type)`

核心引擎，生命周期编排器。

| 属性/方法 | 说明 |
|-----------|------|
| `.registry` | 全局 `Registry` 注册中心 |
| `.startup_order` | 拓扑排序后的启动顺序列表 |
| `await .config(config=Model())` | wiring + config 传播 + on_config 钩子 |
| `await .init()` | on_init 钩子 |
| `await .start()` | 拓扑序调用 on_start |
| `await .stop()` | 逆序调用 on_end |

### `WebCanary(target: type)`

继承自 Canary，仅重写 `start()` 接入 FastAPI + Uvicorn。

按前缀从根模块配置分发参数：`uvicorn_*` → uvicorn，`fastapi_*` → FastAPI()，无前缀为业务配置。服务通过 `self.config` 访问配置。

```python
from pydantic import BaseModel

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

app = WebCanary(MyModule)
await app.config(config=AppConfig())
await app.init()
await app.start()
```

---

## 异常体系

所有框架异常继承自 `CanaryFrameworkError`，可统一捕获：

```python
from canary_framework import (
    CanaryFrameworkError,      # 基类
    ConfigurationError,         # 配置加载/查找失败
    ServiceNotFoundError,       # 服务/模块未注册
    CircularDependencyError,    # 循环依赖
    DependencyInjectionError,   # 依赖注入失败
    LifecycleHookError,         # 生命周期钩子异常
)
```

| 异常 | 触发场景 |
|------|----------|
| `ConfigurationError` | 配置加载或查找失败 |
| `ServiceNotFoundError` | `Registry.get_by_name/class()` 未找到指定服务 |
| `CircularDependencyError` | 拓扑排序检测到环 |
| `DependencyInjectionError` | `inject_deps()` 时依赖实例为 None |
| `LifecycleHookError` | `on_config/init/start/end` 钩子抛出异常 |

---

## 内部架构

```
src/canary_framework/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── _types.py            # ServiceEntry、ServiceMeta、ModuleMeta、RouterMeta
│   ├── enums.py             # LifecycleHook
│   └── exceptions.py        # CanaryFrameworkError 及子类
├── core/
│   ├── __init__.py
│   ├── decorators/
│   │   ├── __init__.py
│   │   ├── lifecycle.py     # @on_config、@on_init、@on_start、@on_end
│   │   ├── module.py        # @module
│   │   ├── service.py       # @service
│   ├── conductor/
│   │   ├── __init__.py
│   │   └── canary.py        # Canary 引擎
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── injector.py      # 依赖注入
│   │   ├── sorter.py        # 拓扑排序
│   │   └── naming.py        # 命名工具 (to_snake)
│   └── container/
│       ├── __init__.py
│       └── registry.py      # 注册中心
└── web/
    └── fastapi/
        ├── __init__.py
        ├── conductor/
        │   ├── __init__.py
        │   └── web_canary.py # WebCanary 引擎
        └── decorators/
            ├── __init__.py
            ├── router.py    # @router、@get、@post……
```

## 初始化流程

```
Canary.config(config=Model())
    │
    ├── wiring()                         阶段0：属性注入
    │   └── 根据字段名匹配 service name，将 config 字段注入实例
    │
    └── on_config()                      阶段1：config 钩子（拓扑序）

Canary.init()
    │
    ├── _collect(target)                 阶段2：递归收集 @service/@module 类
    │   ├── 注册到 Registry
    │   └── 记录 parent_entry
    │
    ├── _validate()                      阶段3：校验依赖完整性
    │
    ├── topological_sort()               阶段4：Kahn 拓扑排序 (O(V+E))
    │
    └── for each in startup_order:       阶段5：按拓扑序初始化
        ├── inject_deps()                setattr 注入依赖
        └── on_init()                    钩子回调
```
