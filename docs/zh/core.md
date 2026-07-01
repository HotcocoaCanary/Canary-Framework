# 架构与内部机制

本页涵盖 Canary Framework 的内部设计、数据流和机制，是面向任务的指南的深入配套文档 —— 使用模式请参阅
[服务](services.md)、[模块](modules.md)、[依赖注入](dependency-injection.md)、
[生命周期](lifecycle.md)和 [Web 与路由](web.md)。

!!! info "重设计后的路由模型"
    路由子系统围绕**单点记忆化组装**重建。如果你还记得旧模型（duck-typing 挂载、每个服务各自的
    `asgi_app` 覆写、在 `startup()` 时生成文档、挂载在 `/{ServiceName}`），请全部忘掉 —— 这些机制
    无一保留。本页只描述当前源码。

## 分层架构 { #layers }

包（`src/canary_framework/`）严格分层，导入只会**向下**流动：

```
common/       零内部依赖 —— 类型、配置、错误、日志
   ↓
engine/       注册表、依赖解析 + 拓扑排序、openapi、参数
   ↓
core/         ServiceBase、ModuleBase、Router（用户继承的基类）
   ↓
decorators/   @service、@module、@config、@before_startup、@before_shutdown
```

- **`common/`** —— 零框架内部依赖。共享枚举与数据类（`RouteInfo`、`ResolvedRoute`、`ServiceMeta`、
  `ModuleMeta`）、`CanaryConfig` 模型、错误层次结构和日志。其余所有模块都可以导入它。
- **`engine/`** —— 仅依赖 `common/` 的运行时机制：`Registry`、依赖解析 + 拓扑排序
  （`dependencies.py`）、OpenAPI schema 生成（`openapi.py`）和参数解析（`params.py`）。
- **`core/`** —— 用户继承的类：`ServiceBase`、`ModuleBase` 以及 `Router` 路由管理器。生命周期、DI
  注入、路由收集和 ASGI 集成都在这里。
- **`decorators/`** —— 公共 API 表面：`@service`、`@module`、`@config`、`@before_startup`、
  `@before_shutdown`。装饰器校验基类继承并附加元数据标记。

!!! note "engine 的位置"
    `engine/` 被 `core/` 导入，因此它在依赖图中位于 `core` 的*上方* —— 这是一个常见的困惑点。
    `engine/` 中没有任何东西导入 `core/` 或 `decorators/`。

## ServiceBase 内部机制 { #servicebase }

`ServiceBase`（`core/service/_base.py`）是所有框架组件的根基类，`ModuleBase` 继承自它。它本身就是一个
ASGI 应用，并持有整条路由组装流水线。`Router` 是作为类属性附加的独立路由管理器。

### 实例状态 { #servicebase-init }

`__init__` 仅设置三个惰性填充的字段，别无其他：

```python
def __init__(self) -> None:
    self._cf_hooks: HookDict | None = None          # 首次调用钩子时发现
    self._cf_parent_registry: object | None = None  # 由父模块在 init 时设置
    self._cf_assembled: Assembled | None = None      # 记忆化的组装结果
    super().__init__()
```

`Assembled` 是携带组装两项产物的 `NamedTuple`：

```python
class Assembled(NamedTuple):
    router: StarletteRouter        # 构建好的路由表
    openapi: dict[str, object]     # OpenAPI 文档
```

### 路由收集 { #servicebase-collect-routes }

`_cf_collect_routes()` 返回本节点的**路由贡献**，类型为 `list[ResolvedRoute]`：

```python
def _cf_collect_routes(self) -> list[ResolvedRoute]:
    router = self._get_router()          # `router` 类属性（若为 Router）
    if router is None:
        return []
    out = []
    for info in router._route_infos:
        bound = info.handler.__get__(self, type(self))   # 将 handler 绑定到本实例
        full_path = router.prefix + info.starlette_path  # 拼接前缀
        while "//" in full_path:                          # 归一化重复的斜杠
            full_path = full_path.replace("//", "/")
        out.append(ResolvedRoute(full_path=full_path, handler=bound, info=info))
    return out
```

每个 `ResolvedRoute` 是**聚合货币**：`full_path`（前缀已拼好）、已绑定到拥有它的实例的 `handler`，以及
原始的 `RouteInfo`。没有 `Router` 的服务贡献空列表。

### 单点组装 { #servicebase-assemble }

`_cf_assemble()` 是本次重设计的核心。无论你运行哪个节点 —— 独立的 `@service` 还是顶层 `@module` ——
都会走这**同一个**方法：

```python
def _cf_assemble(self) -> Assembled:
    resolved = self._cf_collect_routes()          # 1. 收集整个子树
    if not resolved:
        return Assembled(StarletteRouter([]), {})
    _check_route_collisions(resolved)             # 2. 拒绝重复的 (method, full_path)
    cfg = self.config or CanaryConfig()
    routes = [_build_route(r) for r in resolved]  # 3a. 构建一份 Starlette 路由表
    openapi = generate_openapi_schema(resolved, ...)   # 3b. 构建一份 OpenAPI 文档
    routes += _build_doc_routes(openapi, ...)     # 3c. 追加 /openapi.json、/docs、/redoc
    return Assembled(StarletteRouter(routes), openapi)
```

端到端的数据流：

```
_cf_collect_routes()  →  list[ResolvedRoute]         （整个子树，前缀已拼好）
        │
        ├─►  _check_route_collisions   →  重复 (method, full_path) 时抛 ValueError
        │
        ├─►  _build_route（逐条）      →  Starlette Route 表
        │
        └─►  generate_openapi_schema   →  OpenAPI dict  ─►  _build_doc_routes  →  文档端点
                                                                    │
                       StarletteRouter(routes + doc routes)  ◄──────┘
                                    │
                            Assembled(router, openapi)   （缓存于 self._cf_assembled）
```

结果缓存在 `self._cf_assembled`，因此每个节点最多组装**一次**。

!!! tip "独立运行 == 由 module 装配"
    这是核心简化。直接单独运行的服务与被装配进 module 的*同一个*服务，服务的路径**完全相同** ——
    因为两条路径都走这同一个 `_cf_assemble`。唯一的区别是 `_cf_collect_routes()` 遍历的子树范围。
    文档端点只在你实际运行的那个节点上构建**一次**。

### `asgi_app` 与 `openapi()` { #servicebase-asgi-openapi }

两个访问器共享并触发记忆化的组装：

```python
@property
def asgi_app(self) -> StarletteRouter:
    if self._cf_assembled is None:
        self._cf_assembled = self._cf_assemble()
    return self._cf_assembled.router

def openapi(self) -> dict[str, object]:
    if self._cf_assembled is None:
        self._cf_assembled = self._cf_assemble()
    return self._cf_assembled.openapi
```

`openapi()` 是组装后 OpenAPI 文档的公共访问器。组装是**惰性**的 —— 发生在首次访问
`asgi_app`/`openapi()` 时，而这总是在 `init()` 装配好子树*之后*。

### `__call__` —— ASGI 入口点 { #servicebase-call }

`ServiceBase` 是一个 ASGI 应用。`__call__` 只做两件事：

```python
async def __call__(self, scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await self._handle_lifespan(receive, send)   # lifespan → startup/shutdown
    else:
        await self.asgi_app(scope, receive, send)    # 其余一切 → 组装好的路由器
```

`_handle_lifespan` 实现 ASGI lifespan 协议：`lifespan.startup` 消息调用 `self.startup()` 后回复
`lifespan.startup.complete`；`lifespan.shutdown` 消息调用 `self.shutdown()`、回复并返回。

### 生命周期方法 { #servicebase-lifecycle }

| 方法          | 类型  | 作用 |
|--------------|-------|------|
| `init()`     | 同步  | 基类实现仅记日志。`ModuleBase` 覆写它以装配子树。 |
| `startup()`  | 异步  | 通过 `_invoke_hook` 调用 `BEFORE_STARTUP` 钩子。 |
| `shutdown()` | 异步  | 通过 `_invoke_hook` 调用 `BEFORE_SHUTDOWN` 钩子。 |

!!! warning "startup() 不再构建任何东西"
    在旧模型中，`startup()` 会生成 OpenAPI schema 并注册文档端点。现在不再如此。所有路由和文档都由
    `_cf_assemble` 在首次访问 `asgi_app`/`openapi()` 时产生。`startup()` 只触发钩子。

### `_invoke_hook` { #servicebase-invoke-hook }

首次调用时，`_invoke_hook` 通过 `find_hooks()`（`core/service/_hooks.py`）发现钩子 —— 该函数遍历类
MRO，查找带有钩子标记（`__cf_before_startup__`、`__cf_before_shutdown__`）的方法并绑定到实例，结果缓存
于 `_cf_hooks`。若该阶段未注册钩子则静默返回；协程钩子被 await，普通钩子直接调用；钩子抛出的任何异常都会
被包装为 `LifecycleHookError`。

## ModuleBase 内部机制 { #modulebase }

`ModuleBase`（`core/module/_base.py`）继承 `ServiceBase` 并编排子服务。它原样**继承** `_cf_assemble`、
`asgi_app` 和 `openapi()` —— 没有模块专属的 ASGI 覆写。模块与普通服务的差异仅在于 `__init__`、
`init()`、其 `_cf_collect_routes` 覆写以及生命周期传播。

### `__init__` { #modulebase-init-state }

`ModuleBase.__init__` 调用 `super().__init__()`，然后添加注册表/顺序字段，并**立即**实例化 config，
以确保 `log_level` 在任何其他东西运行之前生效：

```python
super().__init__()
self._cf_registry: Registry | None = None
self._cf_startup_order: list[str] = []
self._cf_config: CanaryConfig | None = None

meta = get_module_meta(type(self))
if meta is not None and meta.config_cls is not None:
    self._cf_config = meta.config_cls()
    ensure_logging(self._cf_config.log_level)
else:
    ensure_logging("INFO")
```

### `init()` 流程 { #modulebase-init-flow }

`init()` 是同步的，运行整个装配过程：

```
重置 _cf_assembled  （丢弃任何 init 前缓存的组装）
        ↓
递归注册服务         （_register_entry_with_deps → resolve_deps，含传递依赖）
        ↓
topological_sort    （Kahn 算法 → 启动顺序）
        ↓
实例化 + DI 注入     （entry.cls()；_wire_service；传播 registry + config）
        ↓
初始化每个子项       （按拓扑顺序调用 child.init()）
```

逐步说明：

1. **重置缓存。** 先 `self._cf_assembled = None`，这样任何在 `init()` *之前*记忆化的组装（那时看到的是
   空注册表）就不会污染后续对 `asgi_app`/`openapi()` 的访问。
2. **注册。** `_register_entry_with_deps` 注册 `meta.services` 中的每个类，然后遍历
   `resolve_deps(cls)` 注册每个传递依赖。既非 `@service` 也非 `@module` 装饰的类会抛 `TypeError`。
3. **拓扑排序**，通过 `topological_sort`（见[下文](#topological-sort)）。
4. **在一趟拓扑遍历中实例化并注入。** 对每个名称：`entry.cls()`，然后 `_wire_service(inst, registry)`
   为每个已解析依赖执行 `setattr(inst, attr, dep_instance)`。每个 `ServiceBase` 子项都会被设置
   `_cf_parent_registry`，并在自身没有 config 时继承模块的 `_cf_config`。随后模块自身通过
   `_wire_service(self, registry)` 被注入。
5. **初始化子项。** 按拓扑顺序调用每个子项的 `init()`，最后调用 `super().init()`。

### 模块路由贡献 { #modulebase-collect-routes }

`ModuleBase` 覆写 `_cf_collect_routes`，把自身贡献与每个子项的贡献**折叠**在一起 —— 一次扁平拼接，
**无前缀级联**（每个节点已各自持有自己的前缀）：

```python
def _cf_collect_routes(self) -> list[ResolvedRoute]:
    out = list(super()._cf_collect_routes())        # 模块自身的路由
    for _, child in self._iter_instances(skip_none=True):
        collect = getattr(child, "_cf_collect_routes", None)
        if collect is not None:
            out.extend(collect())                    # 原样拼接每个子项的贡献
    return out
```

由于组装（`_cf_assemble`）继承自 `ServiceBase` 且恰好消费这份列表，模块与服务通过完全相同的代码组装其
路由表。

### 生命周期传播 { #modulebase-lifecycle }

三个阶段都在子项上传播：

- **`init()`** —— 同步；子项按拓扑顺序（在上述注册 + 注入之后）。
- **`startup()`** —— 异步；先触发模块自身的 `BEFORE_STARTUP` 钩子（通过 `super().startup()`），
  然后按**拓扑顺序** await 每个子项的 `startup()`。
- **`shutdown()`** —— 异步；先触发 `BEFORE_SHUTDOWN`，然后按**逆拓扑顺序** await 每个子项的
  `shutdown()`。

## Router 内部机制 { #router }

`Router`（`core/router/_base.py`）是独立的路由管理器 —— **不是** `ServiceBase` 子类。它作为类属性用于
`@service` 或 `@module` 类：

```python
router = Router(prefix="/users", tags=["users"])
```

### 构造器与存储 { #router-constructor }

```python
Router(prefix: str = "", *, tags: list[str] | None = None)
```

- `prefix` —— 拼接到此 router 中每条路由上的 URL 前缀（如 `"/api/v1"`）。
- `tags` —— 自动应用于此 router 下每个端点的 OpenAPI 标签。

router 内部存储 `self._route_infos: list[RouteInfo]`。它持有的是**数据**，而非运行时路由 —— 在组装
之前不绑定、不构建任何东西。

### HTTP 方法装饰器 { #router-decorators }

`@router.get / .post / .put / .delete / .patch` 都委托给 `_http_method`，它会：

1. 用 `parse_route_path(path)` 解析路径 → `(starlette_path, path_params, query_params)`。查询参数来自
   路径字符串的 `?a={a}&b={b}` 部分。
2. 通过 `resolve_params(fn)` 将处理器参数类型解析进 `param_meta`。
3. 自动探测请求体：第一个既非路径参数也非查询参数的处理器参数 —— 若其被 `BaseModel` 子类注解（或显式给出
   `request_model=`）—— 成为 `request_model`，其名字记录为 `body_param`。
4. 构造一个 `RouteInfo` 并追加到 `self._route_infos`。

装饰器返回原始函数不变（不包装）。

可接受的装饰器 kwargs：`summary`、`description`、`response_model`、`request_model`、`tags`、
`deprecated`、`operation_id`、`responses`。（没有 `path_params` / `query_params` kwargs —— 它们由路径
字符串推导得出。）

### 从 `RouteInfo` 到 Starlette 路由 { #router-build }

Router 存储 `RouteInfo`；组装先把它们变成 `ResolvedRoute`
（[`_cf_collect_routes`](#servicebase-collect-routes)），再通过 `_build_route`
（`core/router/_utils.py`）变成 Starlette `Route`。`_build_route` 创建一个 `endpoint` 闭包，它会：

- 从 `request.path_params` 绑定每个**路径参数**并做类型转换；转换失败返回 **400**。
- 从 `request.query_params` 绑定每个**查询参数**并做转换；值无效或缺失必需参数返回 **422**。
- 若设置了 `request_model` + `body_param`，读取 `await request.json()`（JSON 无效 → **400**）并用
  Pydantic 模型校验（`ValidationError` → **422**），将模型传给请求体参数。
- 调用 `await handler(**kwargs)`，并通过 `_auto_response` 转换返回值。

### 冲突检测 { #router-collisions }

`_check_route_collisions(resolved)` 在组装期间对*整个*已收集子树运行。它用一个 `set` 追踪
`(method, full_path)` 对，并在遇到首个重复时抛 `ValueError`：

```python
raise ValueError(f"Route collision: {r.info.method} {r.full_path}")
```

!!! warning "显式前缀 —— 无自动命名空间"
    **没有** `/{ServiceName}` 自动挂载。无前缀的服务在裸路由路径上服务。要为服务加命名空间，请给它的
    router 显式设置 `prefix`（如 `Router(prefix="/users")`）。若两个服务在装配后的树中会服务相同的
    `(method, full_path)`，它们会在组装时发生路径冲突并抛 `ValueError`。

## 依赖注入流程 { #di }

```
resolve_deps(cls)  →  get_type_hints(cls)  →  仅保留携带 CF_SERVICE_MARKER 的类型
        ↓
{attr_name: dep_type}
        ↓
递归注册  →  topological_sort（Kahn）
        ↓
启动顺序: [name1, name2, ...]
        ↓
实例化  →  setattr 注入（_wire_service）  →  生命周期
```

依赖声明为**裸类级类型注解**，而非构造器参数：

```python
@service()
class Auth(ServiceBase):
    db: Database    # ✓ Database 被 @service 装饰（CF_SERVICE_MARKER）—— 注入
    retries: int    # ✗ 普通类型 —— 忽略

# resolve_deps(Auth) → {"db": Database}
```

### `resolve_deps(cls)` { #resolve-deps }

`resolve_deps`（`engine/dependencies.py`）调用 `get_type_hints(cls)`，仅保留类型为携带
`CF_SERVICE_MARKER` 的类（即 `@service`/`@module` 装饰类）的注解。在检查之前，它会通过
`unwrap_optional` 解包 `Optional[T]` / `T | None`。普通类型属性（`name: str`）从不注入。

### `topological_sort(registry)` { #topological-sort }

使用 Kahn 算法：

1. 对所有已注册条目，从 `resolve_deps()` 构建邻接表。
2. 计算每个节点的入度。
3. 用入度为 0 的节点初始化队列。
4. 弹出节点、追加到结果，并递减邻居的入度。
5. 若结果未覆盖每个节点，说明存在环 → `CircularDependencyError`。

Config **不**通过 DI 注入。父模块在 `__init__` 中实例化 `config_cls`，并在 `init()` 期间通过 `.config`
将实例传播给子项。

## 元数据与标记 { #metadata }

装饰器在类上附加元数据标记；这些标记驱动所有框架行为。完整的标记集合位于 `common/types.py`。

### 标记 { #markers }

| 常量                  | 值                       | 用途 |
|----------------------|-------------------------|------|
| `CF_SERVICE_MARKER`  | `"__cf_service__"`      | 在每个 `@service` 和 `@module` 类上为真。 |
| `CF_SERVICE_META`    | `"__cf_service_meta__"` | 存储 `ServiceMeta` / `ModuleMeta` 实例。 |
| `CF_NAME_ATTR`       | `"__cf_name__"`         | 自动生成的组件名称。 |

钩子标记（`__cf_before_startup__`、`__cf_before_shutdown__`）由 `@before_startup` /
`@before_shutdown` 设置在方法上，并映射于 `CF_HOOK_MARKER_MAP`。

### 元类型 { #meta-types }

- **`ServiceMeta(name, config_cls=None)`** —— 由 `@service` 设置。
- **`ModuleMeta(name, services, config_cls=None)`** —— 由 `@module` 设置；扩展 `ServiceMeta`，附带直接
  子服务的 `services` 列表。

### 类型检查 { #type-checks }

```python
def is_cf_service(cls):  # bool(getattr(cls, CF_SERVICE_MARKER, False))
def is_cf_module(cls):   # isinstance(getattr(cls, CF_SERVICE_META, None), ModuleMeta)
```

`is_cf_module` 通过所存元数据的*类型*来区分模块与普通服务：`ModuleMeta` 是 `ServiceMeta` 的子类，因此
模块同时满足两个检查，而普通服务只满足 `is_cf_service`。

## 错误层次结构 { #errors }

所有框架错误都继承自 `CanaryFrameworkError`，因此调用者可以捕获单一类型来处理任何框架错误
（`common/errors.py`）：

```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError          # 配置加载 / 校验失败
    ├── ServiceNotFoundError        # 服务/模块查找失败
    ├── CircularDependencyError     # 拓扑排序检测到环
    ├── DependencyInjectionError    # DI 注入失败（如实例为 None）
    └── LifecycleHookError          # 生命周期钩子抛出未处理异常
```
