# Web Applications

`canary_framework.web` turns a `@cocoa` service into an ASGI web app. It builds on
**Starlette** for routing/requests and **Pydantic v2** for validation and docs, giving a
FastAPI-style developer experience while keeping the same `@cocoa` + `Canary` lifecycle.

```bash
pip install "canary-framework[web]"
```

## Quick start

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService])  # @cocoa + web routes
class LibraryAPI:
    @get("/books/{book_id}")  # path parameter, auto-injected
    async def get_book(self, book_id: int) -> dict:
        return self.book_repository.get(book_id)

    @get("/books")  # query parameter
    async def search(self, q: str = "") -> list[dict]:
        return self.book_repository.search(q)

    @post("/books/{book_id}/borrow")  # Pydantic model = request body
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict:
        return {"result": self.library_service.borrow(body.member_id, book_id)}


app = Canary(LibraryAPI)  # `app` *is* the ASGI application
```

Run it:

```bash
uvicorn examples.library.web:app --reload
```

Open `/docs` (Swagger UI), `/redoc`, or `/openapi.json` for the auto-generated document.

## How parameters are injected

Each handler parameter (after `self`) is bound from the request by name:

| Source | Rule |
|---|---|
| **path** | name matches a `{param}` in the route path (`/books/{book_id}`) |
| **query** | any other scalar, read from the query string (`?q=...`) |
| **body** | the annotation is a Pydantic `BaseModel` subclass → parsed JSON body |
| **request** | the annotation is `starlette.requests.Request` → the raw request |
| **header / cookie** | explicit `Header(...)` / `Cookie(...)` markers |

Scalar values are coerced with Pydantic (`TypeAdapter`), so `book_id: int` receives an
`int` even though the URL supplies a string. A missing required parameter or an invalid
body maps to **HTTP 422**.

Use the `Query` / `Path` / `Header` / `Cookie` / `Body` markers (as a default value or via
`Annotated`) to control the source and metadata explicitly:

```python
from typing import Annotated
from canary_framework.web import get, Query, Header


@get("/items")
async def items(self, limit: Annotated[int, Query(default=10)]) -> list[int]: ...


@get("/whoami")
async def whoami(self, x_token: str = Header(default="")) -> dict: ...
```

Header parameter names map underscores to hyphens (`x_token` → the `x-token` header).

## Responses

Return a `dict`, `list`, or a Pydantic model. The value is validated against the return
annotation and serialized as JSON:

```python
@get("/books/{book_id}")
async def get_book(self, book_id: int) -> Book: ...
```

## Lifecycle

`Canary` drives the same explicit `init()` / `start()` / `stop()` lifecycle for web apps.
Under uvicorn, the ASGI lifespan drives `start()` on startup and `stop()` on shutdown;
`@on_start` / `@on_stop` hooks and cocoa dependency injection (`self.<dep>`) work exactly
as in the core engine. `@web_cocoa` only adds route collection on top.

## Reference

| Decorator / class | Purpose |
|---|---|
| `@web_cocoa(deps=[...], title=..., version=...)` | mark a class as a route holder (a `@cocoa` + web extension) |
| `@get(path)` / `@post(path)` / `@put(path)` / `@patch(path)` / `@delete(path)` / `@route(method, path)` | mark a method as a route handler |
| `Query` / `Path` / `Header` / `Cookie` / `Body` | explicit parameter source + metadata |
| `Canary(*roots)` | the ASGI app / orchestrator |
| `uvicorn app:app` | serve; the ASGI lifespan drives `init()` / `start()` / `stop()` |
