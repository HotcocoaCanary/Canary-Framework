# What's New in 0.9.0

0.9.0 ships the **web extension** and extracts the runtime engine into its own package. The
core model — `@cocoa` units driven by a `Canary` orchestrator — is unchanged from 0.8.0.

## What was added

- **`canary_framework.web`** — expose a `@cocoa` service as an ASGI app:
  - `@web_cocoa(deps=[...], title=..., version=...)` marks a unit as an HTTP route holder.
  - `@get` / `@post` / `@put` / `@patch` / `@delete` / `@route` mark handler methods.
  - Parameters are auto-bound by name — path, query, header, cookie, and Pydantic `BaseModel`
    body — with Pydantic v2 validation (failures map to HTTP 422).
  - Automatic OpenAPI 3.1 at `/openapi.json`, Swagger UI at `/docs`, Redoc at `/redoc`.
- **`canary-framework[web]`** optional dependency (starlette + pydantic + uvicorn).

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


app = Canary(LibraryAPI)  # `app` is the ASGI application
```

## What changed

- **The runtime engine moved** from `core` into `canary_framework.runtime`. `Canary` is now
  also an ASGI application: it drives the lifecycle on `lifespan` and delegates other scopes to
  a serving app a unit exposes during `start()` — by duck typing on a marker, without importing
  any concrete extension.

## Migration from 0.8.0

0.8.0 introduced the current names. For readers coming from the 0.7.0 world, the mapping is:

| 0.7.0 | 0.8.0+ |
|---|---|
| `@canary` | `@cocoa(deps=[...])` |
| `__init__(database: Database)` | `@cocoa(deps=[Database])` |
| `@start` / `@stop` | `@on_start` / `@on_stop` (plus `@on_init`) |
| `Canary.run()` / `Flock` | `Canary(*roots)` |
| `await flock.start()` | `await app.init(); await app.start()` |
| `flock[Database]` | `app[Database]` |
| `async with X.run() as flock` | `async with Canary(X) as app` |

See the [Changelog](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md) for the full history.
