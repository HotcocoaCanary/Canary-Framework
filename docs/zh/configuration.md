# 配置

配置通过 `@config` 装饰器和 `self.config` 访问模式。传入 `app.config(config=...)` 的配置实例会自动传播到模块树中的**每个**服务和模块，作为 `self.config`。

## 定义配置类

使用 `@config` 装饰器标记任何类为配置类。可以是普通 Python 类，也可以是 `pydantic.BaseModel`：

```python
from canary_framework import config

@config
class AppConfig:
    pool_size: int = 10
    timeout: int = 30
    app_name: str = "myapp"
```

也可使用 `pydantic.BaseModel` 进行数据校验：

```python
from pydantic import BaseModel
from canary_framework import config

@config
class AppConfig(BaseModel):
    pool_size: int = 10
    timeout: int = 30
    app_name: str = "myapp"
```

## 在服务中访问配置

树中每个服务和模块通过 `self.config` 访问配置：

```python
@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.config.pool_size, self.config.timeout)
```

## 传入配置

```python
app = Canary(MyRootModule)
await app.config(config=AppConfig())  # wiring + on_config 钩子
await app.init()                       # on_init 钩子
await app.start()
await app.stop()
```

`app.config()` 执行 wiring（依赖注入）、传播配置实例，然后按拓扑序调用所有 `@on_config` 钩子。此时 `self.config` 已可用。

## 服务端和 FastAPI 参数的前缀路由

对 `WebCanary`，根配置模型中以 `uvicorn_` 或 `fastapi_` 开头的字段会自动路由：

- `uvicorn_*` → `uvicorn.Config`
- `fastapi_*` → `FastAPI()` 构造器
- 无前缀 → 业务配置（通过 `self.config` 访问）

```python
@config
class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"     # → uvicorn(host="127.0.0.1")
    uvicorn_port: int = 8000             # → uvicorn(port=8000)
    uvicorn_workers: int = 1             # → uvicorn(workers=1)
    fastapi_title: str = "My API"        # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"       # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None  # → 禁用 docs
    pool_size: int = 10                  # 业务配置字段
```

`WebCanary` 自动按前缀拆分字段，去除前缀后分发给对应消费者。

## 模块级配置

模块可通过 `config=` 参数声明自己的配置类。该模块中的所有服务（以及未声明自身配置的子模块）都接收该模块的配置实例：

```python
@config
class DBModuleConfig:
    dsn: str = "postgres://localhost/test"
    pool_size: int = 5

@module(name="db_module", services=[DBService], config=DBModuleConfig)
class DBModule:
    pass

# DBService.config 为 DBModuleConfig()
```

如果模块未声明 `config=`，则继承最近祖先模块的配置。根配置是最终的兜底。

## 安全：日志脱敏

框架日志自动对敏感字段脱敏。包含 `password`、`secret`、`token`、`key`、`auth`、`credential`、`private` 的字段值在日志中会被替换为 `***`。

```python
@config
class AppConfig(BaseModel):
    db_password: str = "supersecret"     # 日志输出为 db_password='***'
    db_url: str = "postgres://..."       # 正常输出
```
