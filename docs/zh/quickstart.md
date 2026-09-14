# 快速开始

## 安装

```bash
pip install canary-framework
```

需要 Python 3.12 或更高版本。

## 第一个单元

单元是继承了 `Canary` 的普通类。它无参构造，行为写在阶段钩子里。

```python
from canary_framework import Canary, init


class Config(Canary):
    @init
    def load(self) -> None:
        self.dsn = "postgresql://localhost/dev"
```

`@init` 标记的方法在 `init` 阶段运行。钩子可以是同步的，也可以是 `async def`，框架按
返回值判断是否需要等待。

## 声明依赖

用 `dep()` 声明依赖。属性名由你决定：

```python
from canary_framework import Canary, dep, start, stop


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn)

    @stop
    async def close(self) -> None:
        await self.pool.close()
```

`self.config` 的类型是 `Config`，类型检查器与 IDE 都能识别。

## 运行

```python
import asyncio


class UserService(Canary):
    database = dep(Database)


async def main() -> None:
    async with UserService() as service:
        rows = await service.database.pool.fetch("select 1")
        print(rows)


asyncio.run(main())
```

`async with` 进入时依次推进 `init` 与 `start`，退出时回收。整张图（`Config` →
`Database` → `UserService`）自己按依赖顺序就位。

## 四个动作

需要分步控制时用显式写法，效果与 `async with` 一致：

```python
service = UserService()
await service.init()     # 全部 @init
await service.start()    # 全部 @start
await service.stop()     # 逆序全部 @stop
```

未调用 `init()` 就 `start()` 会抛 `LifecycleError`，而不是静默跳过一个阶段。

## 在哪个阶段做什么

- **构造**：不做任何事。单元必须能无参构造，此时依赖尚不可用。
- **`@init`**：只需要依赖、不获取外部资源的准备工作——校验、建索引、计算派生值。
- **`@start`**：获取资源、启动后台任务。只有在此获取的东西才会被 `@stop` 回收。
- **`@stop`**：释放 `@start` 获取的东西。

## 完整示例

仓库的 `examples/library/` 是一个五层的依赖图：

```
LibraryApp → LibraryService → 三个 Repository → Database → Config
```

运行：

```bash
python examples/library/main.py
```

## 接入宿主

框架不认识任何外壳。接进 ASGI、CLI 或消息消费者都是同一种写法：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

service = UserService()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with service:
        yield


app = FastAPI(lifespan=lifespan)
```
