# 0.9.0 新特性

0.9.0 带来了 **web 扩展**，并把运行时引擎抽到独立包。核心模型 —— `@cocoa` 单元 + `Canary`
编排器 —— 与 0.8.0 一致。

## 新增

- **`canary_framework.web`** —— 把 `@cocoa` 服务暴露为 ASGI 应用：
  - `@web_cocoa(deps=[...], title=..., version=...)` 把单元标记为 HTTP 路由持有者。
  - `@get` / `@post` / `@put` / `@patch` / `@delete` / `@route` 标记处理器方法。
  - 参数按名字自动绑定 —— 路径、查询、请求头、Cookie，以及 Pydantic `BaseModel` 请求体 ——
    由 Pydantic v2 校验（失败映射为 HTTP 422）。
  - 自动生成 OpenAPI 3.1（`/openapi.json`）、Swagger UI（`/docs`）、Redoc（`/redoc`）。
- **`canary-framework[web]`** 可选依赖（starlette + pydantic + uvicorn）。

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService])
class LibraryAPI:
    @get("/books/{book_id}")
    async def get_book(self, book_id: int) -> dict: ...

    @post("/books/{book_id}/borrow")
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict: ...


app = Canary(LibraryAPI)  # app 本身就是 ASGI 应用
```

## 变更

- **运行时引擎迁移**：从 `core` 抽到 `canary_framework.runtime`。`Canary` 现在同时是一个
  ASGI 应用：它在 `lifespan` 上驱动生命周期，并把其余 scope 委托给单元在 `start()` 阶段
  暴露的服务入口 —— 通过标记做鸭子类型，不 import 任何具体扩展。

## 从 0.8.0 迁移

0.8.0 引入了现在的命名。对从 0.7.0 世界来的读者，映射如下：

| 0.7.0 | 0.8.0+ |
|---|---|
| `@canary` | `@cocoa(deps=[...])` |
| `__init__(database: Database)` | `@cocoa(deps=[Database])` |
| `@start` / `@stop` | `@on_start` / `@on_stop`（外加 `@on_init`） |
| `Canary.run()` / `Flock` | `Canary(*roots)` |
| `await flock.start()` | `await app.init(); await app.start()` |
| `flock[Database]` | `app[Database]` |
| `async with X.run() as flock` | `async with Canary(X) as app` |

完整历史见 [变更日志](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md)。
