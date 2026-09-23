# 常见用法

常见任务的写法，只用 `Canary`、`dep()` 与阶段。

## 测试替身

继承要替换的单元，在生命周期开始之前把实例登记进作用域。之后图中所有 `dep(Database)` 都
取回这个替身：

```python
import pytest

from canary_framework import scope_of


class FakeDatabase(Database):
    @start
    async def connect(self) -> None:
        self.rows: list[dict] = []

    @stop
    async def close(self) -> None: ...


@pytest.fixture
async def service():
    service = UserService()
    scope_of(service).provide(Database, FakeDatabase())
    async with service:
        yield service


async def test_register(service: UserService) -> None:
    await service.register("ada")
    assert service.database.rows == [{"name": "ada"}]
```

替身运行自己的钩子，进入自己的类声明的依赖。规则见[单元 › 替身](canary.md#substitutes)。

## 按配置选择实现

连接到什么由单元自己决定。从依赖中读取配置，在 `@start` 里选择实现：

```python
import os


class Settings(Canary):
    @init
    def load(self) -> None:
        self.backend = os.environ.get("DB_BACKEND", "sqlite")
        self.url = os.environ.get("DB_URL", "app.db")


class Database(Canary):
    settings = dep(Settings)
    driver: Driver | None = None

    @start
    async def connect(self) -> None:
        match self.settings.backend:
            case "postgres":
                self.driver = PostgresDriver(self.settings.url)
            case "sqlite":
                self.driver = SqliteDriver(self.settings.url)
            case other:
                raise ValueError(f"unknown DB_BACKEND: {other}")
        await self.driver.open()

    @stop
    async def close(self) -> None:
        if self.driver is not None:
            await self.driver.close()
```

其余单元只依赖 `Database`，不需要知道背后是哪个实现。

各个实现应在钩子里构造，而不是各自用 `dep()` 声明：依赖是静态的，声明过的单元无论是否
用到都会被启动。

## 执行到一半失败的钩子

执行到一半抛出的 `@start` 会立即运行本单元的 `@stop`，`start()` 随后释放它启动的依赖。
`@stop` 应只释放实际获取到的资源——上例中 `driver` 默认为 `None` 正是为此。

## 钩子里的阻塞操作

同步钩子在事件循环里执行。耗时的同步钩子会拖住所有与它一起进入的单元，而不只是依赖它的
单元。把阻塞调用放到线程里：

```python
class Index(Canary):
    @init
    async def build(self) -> None:
        self.index = await asyncio.to_thread(build_index, self.corpus.path)
```

很快就能完成的同步钩子——读一个配置、构造一个小对象——保持原样即可。

## 限时关闭

`stop()` 等待每个 `@stop` 完成——依赖者在前，互不依赖的单元同时进行——也会等待仍在进行的
`start()`。需要给关闭设期限时，用 `asyncio.timeout` 包住它：

```python
try:
    async with asyncio.timeout(10):
        await service.stop()
except TimeoutError:
    log.warning("shutdown timed out")
```

到期时正在执行的钩子被取消，不会重试。还没轮到的单元仍持有它获取的东西，再调用一次 `stop()`
会从那里继续回收。

## 接入宿主

框架不认识任何外壳。宿主接收异步上下文管理器时：

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

宿主接收启停回调时，交给它单元的方法：

```python
scheduler.on_startup(service.init, service.start)
scheduler.on_shutdown(service.stop)
```

脚本与命令行：

```python
async def main() -> None:
    async with UserService() as service:
        await service.run_once()


asyncio.run(main())
```

## 重启与重试

`stop()` 会撤销 `start`，因此停止的图可以再次启动。失败的 `start()` 已经释放了它启动的一切，
重试就是再调用一次：

```python
for attempt in range(3):
    try:
        await service.start()
        break
    except ConnectionError:
        if attempt == 2:
            raise
        await asyncio.sleep(2**attempt)
```

`@init` 在一个作用域内只运行一次。见[生命周期 › 再次启动](lifecycle.md#starting-again)。
