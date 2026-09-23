# 为什么选 Canary

Canary 只做一件事：把与应用同寿命的对象连接起来，并运行它们的启动与关闭。本页说明它适合
什么、不适合什么，以及与其他 Python 库的比较。

下面对比表中的每一行都是实测结果，而非凭印象：
[`benchmarks/comparison.py`](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/benchmarks/comparison.py)
用每个库搭建同一张小图并打印结果。可以自己运行：

```bash
uv run benchmarks/comparison.py
```

测量于 2026-09-23，Python 3.13；各库版本固定在脚本头部。

## 适合的场景

- **异步服务、守护进程与后台任务**，其中长寿命对象持有资源——连接池、客户端、后台任务——
  需要按依赖顺序启动与关闭。
- **启动与关闭是对象自身的一部分。** 单元自带 `@start` / `@stop` 钩子；能并发的部分并发启动，
  启动失败时回收已获取的资源，`stop()` 之后可以再次启动。增加阶段只需一行：
  `Phase("migrate", after=init)`。
- **用带类型的属性代替查找。** 对类型检查器来说 `self.db` 就是 `Database`，不需要调用容器，
  也不需要重复写注解。

## 不适合的场景

- **请求级对象。** Canary 在一张图里每个类型只有一个实例，没有请求作用域。每个请求的值交给
  Web 框架——FastAPI 的 `Depends` 与 Canary 配合良好，见下文——或使用带作用域的库，例如 dishka。
- **不能感知任何框架的领域类。** 单元要继承 `Canary`。dishka、dependency-injector 与 injector
  则通过普通类的 `__init__` 注入。
- **同一类型的多个实例，或构造参数。** 单元一律无参构造、每个类型一个；所需的值在 `@init`
  或 `@start` 中从依赖读取。
- **同步程序。** `init()`、`start()` 与 `stop()` 是协程。钩子可以是同步的，但总要有人运行事件
  循环。
- **成熟度。** Canary 还年轻，只有一位维护者。其他库的社区更大，也有现成的 Web 框架集成。

## 对比

场景：`Config`，两个互不依赖、各需 0.1 秒获取的资源 `Database` 与 `Cache`，以及同时需要二者的
`Service`。

| | Canary 1.1.0 | dishka 1.10.1 | dependency-injector 4.49.1 | injector 0.24.0 | FastAPI `Depends` 0.141.1 |
|---|---|---|---|---|---|
| 装配方式 | 类上的 `dep()` 属性 | `Provider` 类 | 由 provider 组成的容器 | module 与 binder | handler 签名中的 `Depends(...)` |
| 你的类 | 继承 `Canary` | 普通类 | 普通类 | 普通类，`__init__` 上加 `@inject` | 普通函数 |
| `mypy --strict` 推断的类型 | `svc.db` 为 `Database` | `get(Service)` 为 `Service` | `service()` 为 `Service`¹ | `get(Service)` 为 `Service` | 取自参数注解 |
| 获取与释放 | `@start` / `@stop` 钩子 | 异步生成器工厂 | `Resource` provider | — | 生成器依赖 |
| 两个互不依赖的资源 | **0.10 秒**，并发 | 0.20 秒，串行 | **0.10 秒**，并发 | — | 0.20 秒，每个请求 |
| 有依赖的资源逆序释放 | 是 | 是 | 是 | — | 是，每个请求 |
| 启动中途失败 | **异常到达调用方之前已释放** | `close()` 时释放 | `shutdown_resources()` 时释放 | — | 每个请求 |
| 关闭后再次启动 | 是 | 是 | 是 | — | — |
| 测试中替换依赖 | `scope_of(root).provide(...)` | 后注册的 `Provider` | `provider.override(...)` | `binder.bind(...)` | `app.dependency_overrides` |
| 请求级或上下文作用域 | **无** | `Scope.REQUEST` | `ContextLocalSingleton` | `threadlocal` | 默认按请求 |
| 安装的第三方包 | 0 | 0 | 0 | 0 | 9 |

¹ 依赖链中有异步资源时，`service()` 在运行时返回一个可等待对象，而静态类型仍是 `Service`；
并且在 `--strict` 下，`await container.init_resources()` 会被报错，因为它的类型是
`Awaitable[None] | None`。

这张表说明了什么、没说明什么：

- **耗时**来自休眠 0.1 秒的资源。它只说明互不依赖的资源是否并发获取，不代表各库本身的快慢。
- **启动中途失败。** 所有带生命周期的库最终都会释放已获取的资源，区别在于由谁触发：Canary
  在 `start()` 内部回滚，只看到异常的调用方无需再清理；dishka 与 dependency-injector 由调用方
  调用 `close()` / `shutdown_resources()` 释放，通常写在 `finally` 里。
- **injector** 没有生命周期 API，生命周期相关的行不适用。
- **FastAPI `Depends`** 是请求级的：每个请求都会获取并释放两个资源。与应用同寿命的对象放在
  应用的 `lifespan` 中，需要自己编写。
- **零依赖并非 Canary 独有。** dishka、dependency-injector 与 injector 同样不安装任何其他包。

## Canary 与 FastAPI 配合

二者分工不同，可以直接配合：Canary 管理与应用同寿命的对象，`Depends` 把每个请求的值交给
handler。

```python
service = LibraryService()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with service:          # 整张图启动，关闭时回收
        yield


app = FastAPI(lifespan=lifespan)


def books() -> BookRepository:
    return service.books         # 与应用同寿命的单元


@app.get("/books/{book_id}")
async def get_book(book_id: int, repo: Annotated[BookRepository, Depends(books)]):
    ...
```

完整版本（含测试）见 [Canary-Framework-Example](https://github.com/HotcocoaCanary/Canary-Framework-Example)
的 `library` 项目，它正是以这种方式构建的 FastAPI 服务。
