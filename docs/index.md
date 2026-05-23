# CF（Canary Framework）Wiki

CF 是一个轻量级 Python 服务框架，核心思想是**服务即最小单元，模块组合服务，模块本身也是服务**。

---

## 目录

1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [服务](#服务)
4. [模块](#模块)
5. [配置](#配置)
6. [生命周期](#生命周期)
7. [依赖注入](#依赖注入)
8. [Web 集成](#web-集成)
9. [API 参考](#api-参考)

---

## 快速开始

### 安装

```bash
pip install cf          # 核心库
pip install cf[web]     # 含 FastAPI 支持的完整安装
```

### 最小示例

```python
import asyncio
from cf import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self):
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

async def main():
    app = Canary(App)
    await app.init()
    await app.start()

asyncio.run(main())
```

不需要 `@config`、`@on_init`、`deps` —— 什么都没有也能跑。

### 完整示例

加上配置、依赖注入、Web 路由：

```python
import asyncio
from cf import service, module, on_init, on_start, Context, config
from cf.web.fastapi import web, get, router, WebCanary

# 配置
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

# 路由
@router(prefix="/api")
class APIRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service

    @get("/hello")
    async def hello(self):
        return await self.svc.greet("world")

# 服务
@web(routers=[APIRouter])
@service(name="HelloService", config=AppConfig)
class HelloService:
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        print("start")

    def greet(self, name: str):
        return f"Hello, {name}!"

# 模块
@web()
@module(name="AppModule", config=AppConfig, services=[HelloService])
class AppModule:
    pass

async def main():
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```

---

## 核心概念

| 概念 | 说明 | 最少声明 | 装饰器 |
|------|------|----------|--------|
| **服务 (Service)** | 最小运行单元 | `@service(name="X")` | `@service` |
| **模块 (Module)** | 服务的组合容器，本身也是服务 | `@module(name="X", services=[...])` | `@module` |
| **上下文 (Context)** | 统一运行时句柄：config / service / resolve | 框架自动传入 | `Context` |
| **配置 (Config)** | pydantic-settings 子类，自动读 .env | 需要时才声明 | `@config` |
| **生命周期 (Lifecycle)** | on_init / on_start / on_end | 需要时才声明 | `@on_init` 等 |

每个服务和模块处于**自己的上下文**中，也存在于**父模块的上下文**中。Context 通过 parent 链向上查找 config 和 resolve。

```
AppModule Context (parent=None)
│  config: AppConfig           # pydantic-settings 自动从 .env 加载
│
├── DBService Context (parent → AppModule)
│   config: AppConfig          # 未声明 config → 沿链找到父模块的
│
├── UserService Context (parent → AppModule)
│   config: UserConfig         # 自己的
│   resolve(DBService) → ✓     # 沿链在父模块 sub_services 中找到
│
└── DataSetService Context (parent → AppModule)
    config: DataSetConfig      # 自己的
    resolve(DBService) → ✓     # 同上
    resolve(UserService) → ✓   # 同上
```

---

## 服务

### 最小写法

```python
from cf import service, on_start

@service(name="HelloService")
class HelloService:
    @on_start
    def start(self):
        print("started")
```

- `name`：全局唯一，必填
- 其他全可选

### 完整写法

```python
from cf import service, on_init, Context

@service(
    name="UserService",         # 必填
    config=UserConfig,          # 可选：@config 装饰的配置类
    deps=[DBService],           # 可选：依赖列表，自动注入为 self.db_service
)
class UserService:
    @on_init
    def init(self, ctx: Context):
        ctx.config.db_url       # 访问配置
        self.db_service.query() # 使用已注入的依赖

    @on_start
    def start(self):
        pass

    @on_end
    def end(self):
        pass
```

---

## 模块

### 最小写法

```python
from cf import module

@module(name="App", services=[SvcA, SvcB])
class App:
    pass
```

### 完整写法

```python
from cf import module, on_init, on_start, Context

@module(
    name="AppModule",
    config=AppConfig,           # 可选：子服务未声明 config 时自动继承
    services=[DBService, UserService],
)
class AppModule:
    @on_init
    def init(self, ctx: Context):
        pass                    # 模块也可以有生命周期钩子

    @on_start
    def start(self):
        pass
```

### config 继承规则

```python
@module(name="DBModule", config=DBConfig, services=[DBService])
class DBModule: ...

@service(name="DBService")              # 未声明 config → 继承父模块的 DBConfig
class DBService: ...
```

---

## 配置

### 最小写法：环境变量直接覆盖默认值

```python
from cf import config

@config
class DBConfig:
    url: str = "postgres://localhost:5432"
    pool_size: int = 10
```

pydantic-settings 自动按优先级读取：**环境变量 > .env 文件 > 默认值**。

`@config` 内置 `env_file=".env"`，无需额外配置：

```bash
# .env 文件
DB_URL=postgres://prod:5432/app
DB_POOL_SIZE=20
```

```python
@on_init
def init(self, ctx: Context):
    ctx.config.url        # → postgres://prod:5432/app
    ctx.config.pool_size  # → 20
```

### 服务器、FastAPI 参数也走配置

根模块的 `@config` 类通过**前缀**区分参数归属：

- `uvicorn_*` → uvicorn.Config / uvicorn.Server
- `fastapi_*` → FastAPI() 构造函数
- 无前缀 → 业务配置（框架不触碰）

```python
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"      # → uvicorn(host="0.0.0.0")
    uvicorn_port: int = 8000            # → uvicorn(port=8000)
    uvicorn_workers: int = 1            # → uvicorn(workers=1)
    fastapi_title: str = "My API"       # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"     # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None # → 关闭文档
    db_url: str = "..."                 # 业务配置（无前缀）
```

WebCanary 自动按前缀拆分、去前缀后分发给对应消费者。

---

## 生命周期

三阶段钩子，全部可选。

```
Canary.init()  → on_init(ctx) → ...   （拓扑序）
Canary.start() → on_start() → ...     （拓扑序）
Canary.stop()  ← on_end() ← ...       （逆序）
```

### on_init(ctx)

接收 Context，此时依赖已注入、配置已加载：

```python
@on_init
def init(self, ctx: Context):
    self.pool = create_pool(ctx.config.db_url)
```

### on_start()

```python
@on_start
async def start(self):
    await self.pool.connect()
```

### on_end()

```python
@on_end
def end(self):
    self.pool.close()
```

钩子可以是 `async def`，框架自动判断并 `await`。

---

## 依赖注入

### 最小写法：声明依赖

```python
@service(name="B", deps=[A])
class B:
    def work(self):
        self.a.do()            # A 自动注入为 self.a
```

### 注入规则

类名 → snake_case → 属性名：

| 依赖类 | 注入为 |
|--------|--------|
| `DBService` | `self.db_service` |
| `UserService` | `self.user_service` |
| `DataSetAdminService` | `self.data_set_admin_service` |

### 注入时机

```
实例化 → 依赖注入 → 配置加载 → on_init(ctx)
```

在 `on_init` 中已可访问所有注入的依赖。

### 启动顺序

Kahn 拓扑排序：被依赖的服务先启动，无依赖的服务最先启动。检测到循环依赖时抛出 `RuntimeError`。

---

## Web 集成

通过 `cf[web]` 和 `WebCanary` 接入 FastAPI。

### 最小 Web 写法

```python
import asyncio
from cf import module
from cf.web.fastapi import web, get, WebCanary

@web()
@module(name="App", services=[])
class App:
    @get("/")
    def index(self):
        return "ok"

async def main():
    app = WebCanary(App)
    await app.init()
    await app.start()

asyncio.run(main())
```

### 完整 Web 写法：服务 + 路由类

```python
from cf import service, on_init, Context
from cf.web.fastapi import web, router, get, post, WebCanary

# 路由类 —— 接收统一 Context
@router(prefix="/api/users")
class UserRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service               # 所属服务实例
        self.db = ctx.resolve(DBService)     # 沿父链查找依赖

    @get("/")
    async def list_users(self):
        return []

    @post("/")
    async def create_user(self, name: str):
        return {"name": name}

# 服务 —— 绑定路由类
@web(routers=[UserRouter])
@service(name="UserService", deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context):
        pass
```

### 统一 Context

路由类的 `__init__` 和服务的 `on_init` 接收**同一个 Context 类**：

- `ctx.config` — 配置（沿 parent 链向上查找）
- `ctx.service` — 所属服务/模块实例
- `ctx.resolve(SomeService)` — 沿 parent 链在父模块的 sub_services 中查找

```python
@router(prefix="/api")
class Router:
    def __init__(self, ctx: Context):
        self.svc = ctx.service           # 调用业务方法
        self.db = ctx.resolve(DBService) # 手动解析依赖
```

### 装饰器速查

| 装饰器 | 用法 |
|--------|------|
| `@web` | `@web()` 或 `@web(routers=[R1, R2])` |
| `@router` | `@router(prefix="/api/users")` |
| `@get` | `@get("/users/{id}")` |
| `@post` | `@post("/users", status_code=201)` |
| `@put` | `@put("/users/{id}")` |
| `@delete` | `@delete("/users/{id}")` |
| `@patch` | `@patch("/users/{id}")` |

---

## API 参考

### 装饰器

#### `@service(name, *, config=None, deps=None)`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称 |
| `config` | `type \| None` | | @config 装饰的配置类 |
| `deps` | `list[type] \| None` | | 依赖的服务类列表 |

#### `@module(name, *, config=None, services=None)`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✓ | 全局唯一名称 |
| `config` | `type \| None` | | 模块的配置类（子服务可继承） |
| `services` | `list[type] \| None` | | 子服务和子模块类列表 |

#### `@config`

将普通类转为 pydantic-settings `BaseSettings` 子类。内置 `env_file=".env"`，优先级：**环境变量 > .env 文件 > 默认值**。

```python
@config
class MyConfig:
    key: str = "default"
```

#### `@on_init` / `@on_start` / `@on_end`

生命周期钩子装饰器。全部可选。钩子方法可以是 `sync` 或 `async`。

---

### 引擎类

#### `Canary(target: type)`

核心引擎，生命周期编排。

```python
app = Canary(MyModule)
await app.init()    # 收集 → 校验 → 排序 → Context 树 → DI → 配置加载 → on_init
await app.start()   # 拓扑序调用 on_start
await app.stop()    # 逆序调用 on_end
```

#### `WebCanary(target: type)`

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

#### `Context(entry, parent, registry)`

统一运行时上下文。通过 parent 链向上委托。

| 属性/方法 | 类型 | 说明 |
|-----------|------|------|
| `.config` | `object` | 配置实例，无则沿链向上查找 |
| `.service` | `object` | 当前上下文绑定的服务/模块实例 |
| `.resolve(cls)` | `object` | 沿 parent 链查找已注册到父模块的服务 |

---

### 内部架构

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

### 初始化流程

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
