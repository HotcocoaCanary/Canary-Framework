# 配置

`canary_framework.config` 只有一个类：`Settings`，既是
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) 的
`BaseSettings`，也是图上的一个单元。

```bash
pip install "canary-framework[config]"
```

!!! note "暂行 API"
    扩展包在稳定之前可能在次版本中调整，见[版本与兼容性](../versioning.md#extensions)。

## 用法

```python
from canary_framework import Canary, dep, start
from canary_framework.config import Settings
from pydantic_settings import SettingsConfigDict


class AppConfig(Settings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    dsn: str = "sqlite://"
    pool_size: int = 5


class Database(Canary):
    config = dep(AppConfig)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn, size=self.config.pool_size)
```

读环境变量、`.env`、类型校验，全部是 pydantic-settings 自己的行为，写法与它的文档完全一致。
`Settings` 增加的只有一件事：它是单元，所以谁要用谁写 `dep(AppConfig)`，整张图共享同一个
实例。

配置无效时，校验错误在 `init` 阶段构造这个配置单元时抛出，此时还没有任何单元运行过 `@start`。

## 无参构造

框架无参构造每个单元，配置也不例外：每个字段都要能从默认值或环境中取到。

## 测试里换一份配置

```python
from canary_framework.test import running

async with running(Service, {AppConfig: AppConfig(dsn="sqlite://:memory:")}) as service:
    ...
```

## 配置自己的依赖与钩子

`Settings` 是普通单元，可以声明依赖与钩子。`dep()` 写在模型里不会被当成字段：

```python
class AppConfig(Settings):
    secrets = dep(SecretStore)

    dsn: str = "sqlite://"
    password: str = ""

    @init
    def load_password(self) -> None:
        self.password = self.secrets.read("db-password")
```

钩子里赋值的属性必须是声明过的字段，这是 pydantic 模型的规则。字段不能叫 `init` / `start` /
`stop`，它们是单元的方法。
