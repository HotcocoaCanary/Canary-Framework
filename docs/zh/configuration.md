# 配置

配置通过 pydantic `BaseModel` 传入 `app.config()`。不再使用 `@config` 装饰器或 `config=` 参数。

## 最小写法

```python
from pydantic import BaseModel

class DBConfig(BaseModel):
    url: str = "postgres://localhost:5432"
    pool_size: int = 10
```

使用环境变量覆盖默认值：

```bash
# .env 文件
DB_URL=postgres://prod:5432/app
DB_POOL_SIZE=20
```

```python
from canary_framework import Canary

app = Canary(RootModule)
await app.config(config=DBConfig())
```

## 字段名匹配

Config 模型的字段名用于匹配 service/module 的 `name`，将对应字段注入为实例属性：

```python
from pydantic import BaseModel
from canary_framework import service, on_config

class DBConfig(BaseModel):
    pool_size: int = 10
    timeout: int = 30

class AppConfig(BaseModel):
    db: DBConfig = DBConfig()          # 字段名 = service name → 注入到 DBService
    user: dict = {"max_items": 100}    # 也可以传 dict

@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.pool_size)    # pool_size 通过字段名匹配注入
        self.conn = connect(timeout=self.timeout)
```

## 完整示例

```python
from pydantic import BaseModel
from canary_framework import Canary, service, module, on_config

class DBConfig(BaseModel):
    pool_size: int = 10
    timeout: int = 30

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    db: DBConfig = DBConfig()
    user: dict = {"max_items": 100}

@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.pool_size)

@service(name="user")
class UserService:
    @on_config
    def setup(self) -> None:
        self.max_items = self.max_items

@module(name="app", services=[DBService, UserService])
class AppModule:
    pass

app = Canary(AppModule)
await app.config(config=AppConfig())
await app.init()
```

## 属性注入规则

- Config 模型中的每个字段，框架根据字段名匹配 service/module 的 `name`
- 匹配成功后，config 字段被直接注入到服务实例上（字段名 = 属性名）
- 服务可以直接通过 `self.<field>` 访问，无需通过嵌套模型属性
- 字段值可以是 `BaseModel` 子类（递归展开）或普通 `dict`

## 安全：日志脱敏

框架日志自动对敏感字段脱敏。包含 `password`、`secret`、`token`、`key`、`auth`、`credential`、`private` 的字段值在日志中会被替换为 `***`。
