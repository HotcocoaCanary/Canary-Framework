# 核心概念

本文档涵盖 Canary Framework 的内部设计、数据流和机制。

## 设计概述

Canary Framework 遵循三层架构：

```
 common/  ──►  core/  ──►  decorators/  ──►  engine/
(类型,           (ServiceBase,   (公共 API:        (注册表,
 配置,            ModuleBase,     @service,        依赖,
 错误,            Router)         @module,          钩子,
 路由)                            @config,          OpenAPI,
                                 生命周期           参数,
                                 钩子)              日志)
```

- **common/** — 零框架内部依赖。类型、配置模型、错误层次结构和路由解析，每个其他模块都导入这些。
- **core/** — 两个基类（`ServiceBase`、`ModuleBase`）和 `Router` 类，提供生命周期、DI 注入、路由管理和 ASGI 集成。
- **decorators/** — 公共 API。装饰器验证基类继承、附加元数据标记并自动生成名称。
- **engine/** — 运行时机制：注册表、拓扑排序、钩子发现、OpenAPI 生成、参数解析和日志。

## ServiceBase 内部机制

`ServiceBase`（core/service/_base.py）是所有框架组件的根基类。ModuleBase 继承自它。`Router` 类是独立的 Route 管理器，作为类属性在服务上使用。

### `__init__`

```python
def __init__(self):
    self._cf_hooks: HookDict | None = None     # 懒加载发现的钩子
    self._cf_parent_registry: object | None = None  # 由父模块注入
```

### 生命周期方法

| 方法 | 签名 | 作用 |
|---|---|---|
| `init()` | `() → None` | 设置日志和配置。 |
| `startup()` | `() → None` | 调用 `BEFORE_STARTUP` 钩子。 |
| `shutdown()` | `() → None` | 调用 `BEFORE_SHUTDOWN` 钩子。 |

### `__call__` — ASGI 3 接口

```python
async def __call__(self, scope, receive, send):
    if scope["type"] == "lifespan":
        await self._handle_lifespan(receive, send)
    else:
        asgi = getattr(self, "asgi_app", None)
        if asgi is not None:
            await asgi(scope, receive, send)
```

将 ASGI lifespan 事件映射到 `startup()`/`shutdown()`。非 lifespan 请求在可用时委托给 `self.asgi_app`（由子类设置）。

### `_handle_lifespan`

实现 ASGI lifespan 协议：

1. 接收 `lifespan.startup` → 调用 `self.startup()` → 发送 `lifespan.startup.complete`
2. 接收 `lifespan.shutdown` → 调用 `self.shutdown()` → 发送 `lifespan.shutdown.complete` → 退出

### `_invoke_hook`

通过 `()`（engine/hooks.py）进行懒加载钩子发现。首次调用时，`()` 遍历类 MRO 查找标记了钩子标记（`__cf_before_startup__`、`__cf_before_shutdown__`）的方法，并将其绑定到实例。支持同步和异步钩子。钩子引发的任何异常都会被包装在 `CanaryFrameworkError` 中。

## ModuleBase 内部机制

`ModuleBase`（core/module.py）继承 `ServiceBase` 并编排子服务。

### `init()` 流程

```
递归注册服务
    ↓
topological_sort（Kahn 算法）
    ↓
按顺序实例化服务
    ↓
DI 注入：resolve_deps → setattr 注入
    ↓
在所有 ServiceBase 子项上设置 _cf_parent_registry
    ↓
按顺序初始化每个子项
```

**逐步说明：**

1. **注册**（`_register_entry_with_deps`）：对于模块 `services` 列表中的每个服务，在注册表中注册它。对于每个已注册的服务，调用 `resolve_deps(cls)` 发现注解声明的依赖并递归注册它们。

2. **拓扑排序**（`topological_sort`）：使用 Kahn 算法。从 `resolve_deps()` 输出构建依赖图，计算入度，生成有效的启动顺序。检测循环依赖。

3. **实例化**：通过 `entry.cls()` 按拓扑顺序创建所有已注册类的实例。

4. **DI 注入**：对于每个实例，`resolve_deps(type(inst))` 返回 `{attr_name: dep_type}`。对于每个依赖，`setattr(inst, attr_name, registry.get_by_class(dep_type).instance)` 注入已解析的实例。注解键名成为属性名。

5. **父注册表注入**：`inst._cf_parent_registry = registry` 在每个 `ServiceBase` 实例上设置。Router 通过此方式访问同级 RouterMeta，Agent 通过此方式访问注册表。

6. **子项初始化**：每个子项的 `init()` 按拓扑顺序调用。Config 从 `services` 列表自动发现 — 任何通过 `issubclass(CanaryConfig)` 的类被视为配置。

### `asgi_app` 属性

懒加载构建 Starlette `Router`，按启动顺序遍历子服务：

- **Duck-typing 挂载**：如果 `hasattr(inst, "asgi_app")`，则子项通过 Starlette `Mount` 挂载在其 `get_mount_path()`（或 `f"/{name}"` 回退）上。
- **根路由**：如果 `hasattr(inst, "_cf_get_root_routes")`，子项的根路由列表贡献给模块级别的 Router。Router 通过此方式在根级别提供 `/docs`、`/redoc`、`/openapi.json`。

挂载路径冲突会被检测并抛出 `ValueError`。

### 生命周期传播

所有生命周期方法（init、startup、shutdown）传播到子项：
- **正向顺序**（拓扑）：init、startup
- **反向顺序**：shutdown

## Router 内部机制

`Router`（core/router/_base.py）是独立的 Route 管理器，不是 `ServiceBase` 子类。它作为类属性在 `@service()` 或 `@module()` 装饰类上使用。

### 构造器

```python
Router(prefix: str = "", *, tags: list[str] | None = None)
```

- `prefix` — 应用于此 Router 中所有路由的 URL 前缀（如 `"/api"`）
- `tags` — 自动应用于此 Router 中所有端点的 OpenAPI 标签

内部存储 `self._route_infos: list[RouteInfo]`，随着通过方法装饰器注册路由而填充。

### HTTP 方法装饰器

每个 `Router` 实例提供方法装饰器（`@router.get`、`@router.post`、`@router.put`、`@router.delete`、`@router.patch`），内部注册 `RouteInfo` 对象：

1. 通过 `parse_route_path(path)` 解析路径 → 拆分为 `starlette_path`、`path_params`、`query_params`
2. 通过 `resolve_params(fn)` 解析处理器参数类型
3. 从处理器注解自动检测 `request_model`
4. 构造包含所有元数据的 `RouteInfo` 数据类
5. 追加到 `self._route_infos`

装饰器返回原始函数不变（不包装）。

### 路由收集

`_collect_routes()` 是一个自由函数，适用于任何对象实例：

1. 读取 `getattr(instance, "router", None)` — 如果是 `Router`，遍历 `router._route_infos`
2. 对于每个 `RouteInfo`，调用 `_route_handler()` 创建 Starlette `Route`

### `_route_handler`

1. 从 `RouteInfo` 读取路由元数据
2. 创建 `endpoint` 闭包：
   - 从 `request.path_params` 绑定路径参数，进行类型转换
   - 从 `request.query_params` 绑定查询参数，进行类型转换
   - 如果设置了 `request_model`，调用 `await request.json()` 并用 Pydantic 解析
   - 调用 `await handler(...)` 传入解析的 kwargs
   - 通过 `_auto_response()` 转换返回值
3. 返回 `Route(starlette_path, endpoint=endpoint, methods=[method])`

### OpenAPI 文档

模块中第一个带 `Router` 的服务在 `startup()` 时生成文档：

1. 从自身和通过 `_cf_parent_registry` 的所有同级服务收集 `RouteInfo`
2. 调用 `generate_openapi_schema()` 传入所有路由信息和配置值
3. 生成 Swagger UI 和 ReDoc HTML 页面
4. 为 `/docs`、`/redoc`、`/openapi.json` 创建根路由
5. 先到先得注册：只有模块中的第一个 Router 注册文档

### 挂载路径

带 `Router` 的服务如果设置了 `router.prefix`（如 `"/api"`）则挂载在其上，否则挂载在 `f"/{service_name}"`。

## 依赖注入流程

```
resolve_deps(cls) → __annotations__ → 按 CF_SERVICE_MARKER 过滤
    ↓
{attr_name: dep_type}
    ↓
递归注册 → topological_sort（Kahn）
    ↓
startup_order: [name1, name2, ...]
    ↓
实例化 → setattr 注入 → 生命周期
```

### `resolve_deps(cls)`

通过 `typing.get_type_hints()` 读取 `cls.__annotations__`，仅返回类型设置了 `CF_SERVICE_MARKER`（即被 `@service` 或 `@module` 装饰的类）的条目：

```python
# 对于类：
@service()
class Auth(ServiceBase):
    db: Database   # ✓ CF_SERVICE_MARKER — 包含
    x: int         # ✗ 不是服务 — 排除

# resolve_deps(Auth) → {"db": Database}
```

### `topological_sort(registry)`

使用 Kahn 算法：

1. 从 `resolve_deps()` 构建邻接表
2. 计算每个节点的入度
3. 将入度为 0 的节点加入队列
4. 处理队列，减少入度
5. 如果未处理全部节点 → `CircularDependencyError`

## 元数据系统

装饰器在类上设置元数据标记。这些标记驱动所有框架行为。

### 标记

| 常量 | 值 | 用途 |
|---|---|---|
| `CF_SERVICE_MARKER` | `"__cf_service__"` | 在所有 `@service` 和 `@module` 类上设置为 `True` |
| `CF_SERVICE_META` | `"__cf_service_meta__"` | 存储 `ServiceMeta` / `ModuleMeta` / `RouterMeta` 实例 |
| `CF_NAME_ATTR` | `"__cf_name__"` | 自动生成的名称（如 `"DatabaseService"`） |
| `ROUTE_ATTR` | `"__cf_route__"` | HTTP 处理器方法上的路由元数据字典 |
| `CF_CONFIG_MARKER` | `"__cf_config__"` | 在 `@config` 类上设置为 `True` |

### 元类型

- **`ServiceMeta(name)`** — 由 `@service` 设置
- **`ModuleMeta(name, services)`** — 由 `@module` 设置，继承 `ServiceMeta`
- **`RouterMeta(name, prefix, tags, routes)`** — 由 `Router` 类设置，继承 `ServiceMeta`

### 类型检查

`is_cf_service`、`is_cf_module` 和 `is_cf_router` 对存储在 `CF_SERVICE_META` 中的元类型使用 `isinstance` 检查：

```python
def is_cf_service(cls):  # hasattr(cls, CF_SERVICE_MARKER)
def is_cf_module(cls):   # isinstance(getattr(cls, CF_SERVICE_META, None), ModuleMeta)
def is_cf_router(cls):   # isinstance(getattr(cls, CF_SERVICE_META, None), RouterMeta)
```

## ASGI 集成

1. **`ServiceBase.__call__`** — 处理 ASGI lifespan 协议（startup/shutdown 事件）。将非 lifespan 请求委托给 `asgi_app`。

2. **`ModuleBase.asgi_app`** — 通过 duck-typing 聚合子 ASGI 应用。将带有 `asgi_app` 的子项挂载在其挂载路径上。将带有 `_cf_get_root_routes()` 的子项的根路由贡献出去。

3. **`Router.asgi_app`** — 第一个带有 `Router` 属性的服务从收集的路由处理器（通过 `_collect_routes()`）构建 Starlette `Router`。在 `startup()` 时，生成 OpenAPI schema 并将文档端点注册为根路由（先到先得）。

## 错误处理

```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError            # 配置加载/验证失败
    ├── ServiceNotFoundError          # 服务查找失败
    ├── CircularDependencyError       # 拓扑排序检测到循环
    ├── DependencyInjectionError      # DI 注入失败（None 实例等）
    └── CanaryFrameworkError            # 钩子引发未处理异常
```

所有框架错误继承自 `CanaryFrameworkError`，调用者可以捕获单一类型来处理所有框架错误。
