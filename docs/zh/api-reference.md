# API 参考

## 装饰器

### `@service(name, *, config=None, deps=None)`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称 |
| `config` | `type \| None` | | @config 装饰的配置类 |
| `deps` | `list[type] \| None` | | 依赖的服务类列表 |

### `@module(name, *, config=None, services=None)`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称 |
| `config` | `type \| None` | | 模块的配置类（子服务可继承） |
| `services` | `list[type] \| None` | | 子服务和子模块类列表 |

### `@config`

将普通类转为 pydantic-settings `BaseSettings` 子类。内置 `env_file=".env"`，优先级：**环境变量 > .env 文件 > 默认值**。

```python
@config
class MyConfig:
    key: str = "default"
```

### `@on_init` / `@on_start` / `@on_end`

生命周期钩子装饰器。全部可选。钩子方法可以是 `sync` 或 `async`。

---

## 引擎类

### `Canary(target: type)`

核心引擎，生命周期编排。

```python
app = Canary(MyModule)
await app.init()    # 收集 → 校验 → 排序 → Context 树 → DI → 配置加载 → on_init
await app.start()   # 拓扑序调用 on_start
await app.stop()    # 逆序调用 on_end
```

### `WebCanary(target: type)`

继承自 Canary，仅重写 `start()` 接入 FastAPI + Uvicorn。按前缀从根模块 @config 分发参数：`uvicorn_*` → uvicorn，`fastapi_*` → FastAPI()。

```python
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"
    fastapi_version: str = "1.0.0"

app = WebCanary(MyModule)
await app.init()
await app.start()
```

### `Context(entry, parent, registry)`

统一运行时上下文。通过 parent 链向上委托。

| 属性/方法 | 类型 | 说明 |
|-----------|------|------|
| `.config` | `object` | 配置实例，无则沿链向上查找 |
| `.service` | `object` | 当前上下文绑定的服务/模块实例 |
| `.resolve(cls)` | `object` | 沿 parent 链查找已注册到父模块的服务 |

---

## 内部架构

```
cf/
├── core/
│   ├── decorators/          # 用户面向的装饰器
│   │   ├── config.py        # @config（内置 env_file=".env"）
│   │   ├── service.py       # @service
│   │   ├── module.py        # @module
│   │   └── lifecycle.py     # @on_init, @on_start, @on_end
│   ├── engine/
│   │   ├── canary.py        # Canary 引擎（启动编排 + Context 树构建）
│   │   ├── context.py       # Context（统一上下文，parent 链查找）
│   │   ├── injector.py      # 依赖注入
│   │   └── sorter.py        # 拓扑排序
│   ├── registry/
│   │   └── registry.py      # 注册中心（ServiceEntry + Registry）
│   └── utils/
│       └── naming.py        # 命名工具（CamelCase → snake_case）
│
└── web/
    └── fastapi/
        ├── web_canary.py    # WebCanary 引擎（继承 Canary）
        └── decorators/
            ├── web.py       # @web
            └── router.py    # @router, @get, @post, ...
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
    ├── topological_sort()       阶段2：Kahn 拓扑排序
    │
    ├── _build_context_tree()    阶段3：按模块树构建 Context parent 链
    │
    └── for each in startup_order:   阶段4：按拓扑序初始化
        ├── inject_deps()            setattr 注入依赖
        ├── config_cls()             直接实例化（pydantic-settings 自动读 .env）
        └── on_init(entry.context)   钩子回调
```
