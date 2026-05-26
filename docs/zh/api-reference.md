# API 参考

## 装饰器

### `@service(name, *, config=None, deps=None)`

将类声明为 CF 框架的服务（最小运行单元）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称，用于依赖声明和名称索引 |
| `config` | `type \| None` | | `@config` 装饰的配置类，None 时从父模块继承 |
| `deps` | `list[type] \| None` | | 依赖的服务类列表，自动注入为 snake_case 属性 |

### `@module(name, *, config=None, services=None)`

将类声明为 CF 框架的模块（服务的组合容器）。模块本身也是服务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称 |
| `config` | `type \| None` | | 模块的配置类（子服务未声明时继承） |
| `services` | `list[type] \| None` | | 子服务和子模块类列表 |

### `@config`

将普通类转为 pydantic-settings `BaseSettings` 子类。内置 `env_file=".env"`。

优先级：**环境变量 > .env 文件 > 默认值**。

```python
@config
class MyConfig:
    key: str = "default"
```

### 生命周期钩子

| 装饰器 | 签名 | 执行顺序 | 说明 |
|--------|------|----------|------|
| `@on_init` | `(ctx: Context)` | 拓扑序 | 依赖已注入、配置已加载 |
| `@on_start` | `()` | 拓扑序 | 无参数 |
| `@on_end` | `()` | 逆序 | 无参数 |

钩子方法可以是 `sync` 或 `async`，框架通过 `asyncio.iscoroutine` 自动适配。

### `LifecycleHook` 枚举

```python
from canary_framework import LifecycleHook

LifecycleHook.INIT   # "on_init"
LifecycleHook.START  # "on_start"
LifecycleHook.END    # "on_end"
```

---

## 引擎类

### `Canary(target: type)`

核心引擎，生命周期编排。

| 属性/方法 | 说明 |
|-----------|------|
| `.registry` | 全局 `Registry` 注册中心 |
| `.startup_order` | 拓扑排序后的启动顺序列表 |
| `await .init()` | 收集 → 校验 → 拓扑排序 → Context 树 → DI → 配置加载 → on_init |
| `await .start()` | 拓扑序调用 on_start |
| `await .stop()` | 逆序调用 on_end |

### `WebCanary(target: type)`

继承自 Canary，仅重写 `start()` 接入 FastAPI + Uvicorn。

按前缀从根模块 `@config` 分发参数：`uvicorn_*` → uvicorn，`fastapi_*` → FastAPI()，无前缀为业务配置。

```python
@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

app = WebCanary(MyModule)
await app.init()
await app.start()
```

### `Context`

统一运行时上下文。通过 parent 链向上委托配置和依赖解析。

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `.get_config(type[T])` | `T` | **类型安全**的配置访问，沿 parent 链查找 |
| `.get_service(type[T])` | `T` | **类型安全**的服务实例访问 |
| `.resolve(type[T])` | `T` | 在模块树中定位并返回服务实例 |

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
| `ConfigurationError` | `ctx.get_config()` 未找到配置实例 |
| `ServiceNotFoundError` | `Registry.get_by_name/class()` 未找到，`ctx.resolve()` 未找到 |
| `CircularDependencyError` | 拓扑排序检测到环 |
| `DependencyInjectionError` | `inject_deps()` 时依赖实例为 None |
| `LifecycleHookError` | `on_init/start/end` 钩子抛出异常 |

---

## 内部架构

```
src/canary_framework/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── _types.py            # ServiceEntry, ServiceMeta, ModuleMeta
│   ├── enums.py             # LifecycleHook
│   └── exceptions.py        # CanaryFrameworkError & 子类
├── core/
│   ├── __init__.py
│   ├── decorators/
│   │   ├── __init__.py
│   │   ├── config.py        # @config（内置 env_file=".env"）
│   │   ├── lifecycle.py     # @on_init, @on_start, @on_end
│   │   ├── module.py        # @module
│   │   └── service.py       # @service
│   ├── conductor/
│   │   ├── __init__.py
│   │   ├── canary.py        # Canary 引擎
│   │   └── context.py       # Context
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── injector.py      # 依赖注入
│   │   ├── sorter.py        # 拓扑排序
│   │   └── naming.py        # 命名工具
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
            ├── router.py    # @router, @get, @post, ...
            └── web.py       # @web
```

## 初始化流程

```
Canary.init()
    │
    ├── _collect(target)         阶段0：递归收集 @service/@module 类
    │   ├── 注册到 Registry
    │   ├── 记录 parent_entry
    │   └── config_cls 继承
    │
    ├── _validate()              阶段1：校验依赖完整性
    │
    ├── topological_sort()       阶段2：Kahn 拓扑排序（O(V+E)）
    │
    ├── _build_context_tree()    阶段3：按模块树构建 Context parent 链
    │
    └── for each in startup_order:   阶段4：按拓扑序初始化
        ├── inject_deps()            setattr 注入依赖
        ├── config_cls()             直接实例化（pydantic-settings 自动读 .env）
        └── on_init(entry.context)   钩子回调
```
