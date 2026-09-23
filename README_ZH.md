<h1 align="center">Canary Framework</h1>

<p align="center">
  面向普通 Python 类的<strong>依赖注入</strong>与<strong>生命周期</strong>框架
  —— 纯标准库，零依赖。
</p>

<p align="center">
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="PyPI" src="https://img.shields.io/pypi/v/canary-framework.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/canary-framework.svg"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/canary-framework.svg"></a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="https://hotcocoacanary.github.io/Canary-Framework/">文档</a> ·
  <a href="CHANGELOG.md">变更日志</a>
</p>

## 安装

```bash
pip install canary-framework
```

需要 Python 3.12 或更高版本。安装不会引入任何第三方包。

## 模型

继承 `Canary` 即为一个**单元**：用 `dep()` 声明它依赖谁，用 `@init` / `@start` / `@stop`
声明它在各阶段做什么。启动一个单元，它的依赖按依赖顺序就位；退出时逆序回收。

```python
import asyncio

from canary_framework import Canary, dep, init, start, stop


class Config(Canary):
    @init
    def load(self) -> None:
        self.dsn = "postgresql://localhost/dev"


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        print(f"连接 {self.config.dsn}")

    @stop
    async def close(self) -> None:
        print("断开连接")


class UserService(Canary):
    database = dep(Database)


async def main() -> None:
    async with UserService() as service:
        print(service.database.config.dsn)


asyncio.run(main())
```

```
连接 postgresql://localhost/dev
postgresql://localhost/dev
断开连接
```

## 两条规则

**进入**依赖在前：一个单元进入某个阶段之前，它的依赖已经完成该阶段。同一个单元的同一个
阶段只运行一次，无论有多少单元依赖它；互不依赖的单元同时进入。

**释放**本单元在前：停止一个单元时先停止它——除非它仍被使用——再以同样的方式尝试它的依赖，
不再被其他单元使用的依赖随之停止。失败的 `start()` 在抛出之前释放它启动的一切。

两条规则都运行在依赖图上。依赖图在任何钩子运行之前构建，环也在这时被发现。

`init` / `start` / `stop` 是这两条规则的三个名字。加第四个阶段只需要一行：
`Phase("migrate", after=init)`。

## 亮点

- **类型完整。** `self.config` 就是 `Config`，`async with service` 交出你自己的类型，
  `dep(不是单元的类)` 是一个类型错误。不需要任何插件。
- **普通类。** 装饰器只在方法上打标记；单元可继承、可混入、可嵌套，生命周期方法也可以
  覆盖并用 `super()` 组合。
- **失败路径是设计的一部分。** `start()` 失败会先释放它启动的单元再抛出；`stop()` 是唯一的回收
  路径，正常结束与失败结束共用，重复调用幂等。停止的图可以再次启动，失败的进入可以重试。
- **不靠 mock 的测试替身。** `scope_of(service).provide(Database, FakeDatabase())` 在整张图上
  替换一个依赖，替身走自己的生命周期。
- **默认并发。** 互不依赖的单元同时启动、同时停止，由依赖图调度。
- **零依赖。** 有一条测试断言：跑完一整轮生命周期，不会从 site-packages 导入任何东西。

## 接入宿主

框架不认识任何外壳 —— HTTP、CLI、定时任务、消息消费者都由你决定：

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with service:
        yield


app = FastAPI(lifespan=lifespan)
```

## 稳定性

1.0 是第一个稳定版本。公开 API 遵循
[语义化版本](https://hotcocoacanary.github.io/Canary-Framework/zh/versioning/)：2.0 之前不做
破坏性变更，任何移除都至少提前一个次版本弃用。

## 文档

- [为什么选 Canary](https://hotcocoacanary.github.io/Canary-Framework/zh/why-canary/)——适合与不适合的
  场景，以及与 dishka、dependency-injector、injector、FastAPI `Depends` 的实测对比
- [文档站](https://hotcocoacanary.github.io/Canary-Framework/zh/)——
  [1.1 新特性](https://hotcocoacanary.github.io/Canary-Framework/zh/whats-new/)、
  [常见用法](https://hotcocoacanary.github.io/Canary-Framework/zh/patterns/)、
  [从 0.9.x 升级](https://hotcocoacanary.github.io/Canary-Framework/zh/upgrading-from-0.9/)
- 完整示例——FastAPI 服务与常驻守护进程：
  [Canary-Framework-Example](https://github.com/HotcocoaCanary/Canary-Framework-Example)
  （以子模块挂在 [`examples/`](examples)）

## 社区

提问与想法请到 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions)，
bug 请提 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues)。另见
[贡献指南](CONTRIBUTING.md)、[项目治理](GOVERNANCE.md) 与 [安全策略](SECURITY.md)。

## 许可证

Apache-2.0，见 [LICENSE](LICENSE)。
