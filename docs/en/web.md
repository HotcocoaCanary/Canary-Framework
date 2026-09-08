# Web Apps

`canary_framework.web` exposes `@cocoa` services directly as an ASGI web app. It uses
**Starlette** for routing and requests and **Pydantic v2** for validation and documentation,
while keeping the same `@cocoa` + `Canary` lifecycle.

```bash
pip install "canary-framework[web]"
```

## Getting started

```python
from pydantic import BaseModel
from canary_framework import Canary
from canary_framework.web import get, post, web_cocoa


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService], prefix="/api", tags=["library"])
class LibraryAPI:
    @get("/books/{book_id}")                        # matches a placeholder → path param
    async def get_book(self, book_id: int) -> dict:
        return self.book_repository.get(book_id)

    @get("/books")                                  # scalar → query param
    async def search(self, q: str = "") -> list[dict]:
        return self.book_repository.search(q)

    @post("/books/{book_id}/borrow", status_code=201)   # model → request body
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict:
        return {"result": self.library_service.borrow(body.member_id, book_id)}


app = Canary(LibraryAPI)  # `app` is the ASGI app
```

Run it:

```bash
uvicorn examples.library.web:app --reload
```

Open `/docs` (Swagger UI) or `/openapi.json` for the generated document.

**Handlers must be `async def`.** A synchronous function runs on the event loop thread and
stalls the whole process, not just its own request — the framework will not silently offload it
to a thread pool (that would make "where does this code run" implicit), it refuses at assembly
time instead. Yield explicitly for blocking calls:
`await asyncio.to_thread(blocking_call, ...)`.

## Where parameters come from

There is one inference rule: **scalars come from the query string (or the path when the name
matches a placeholder); everything else comes from the body.**

| Source | Rule |
|---|---|
| **path** | the parameter name matches a `{param}` in the route path |
| **query** | any other scalar — a type that can be reconstructed from a single string, plus `list` / `Union` of those |
| **body** | everything else: Pydantic models, `dict`, `list[Model]`, … |
| **request** | annotated as `starlette.requests.Request` → the raw request object |
| **header / cookie** | explicit only, see below |

Scalars are converted by Pydantic, so `book_id: int` really is an `int` even though the URL
carries a string.

### Headers and cookies

These are the only two sources inference cannot reach — `x: str` gives no hint whether it wants
`X-Token` or `?x=` — so they must be said explicitly:

```python
from typing import Annotated
from canary_framework.web import Cookie, Header, get


@get("/whoami")
async def whoami(
    self,
    x_token: Annotated[str, Header()] = "anonymous",
    session: Annotated[str, Cookie(alias="sid")] = "",
) -> dict: ...
```

Header names map underscores to hyphens (`x_token` → `x-token`); `alias` covers the cases where
the wire name and the parameter name differ. `Header` / `Cookie` also take `description=`, which
lands in the OpenAPI document.

**Markers only go inside `Annotated`**, and the default value goes where defaults belong.
Writing `x_token: str = Header()` is refused at assembly time — it would make the default-value
position mean two things at once.

There are no `Query` / `Path` / `Body` markers: inference already gives the same answer, and
saying it twice is just repetition.

### Constraints

Pydantic metadata inside `Annotated` is preserved in full — it both validates and documents:

```python
from pydantic import Field


@get("/items")
async def items(self, page: Annotated[int, Field(gt=0, le=100)] = 1) -> dict: ...
```

`?page=-5` gets a 422, and the schema in the document carries `exclusiveMinimum: 0`.

### Request bodies

A request has exactly one body, so **a handler may have only one body parameter** — two are
refused at assembly time. The framework does not silently nest them by parameter name.

A body parameter with a default is an **optional body**:

```python
@post("/items")
async def create(self, item: Item | None = None) -> dict:
    return {"got": item is not None}
```

## Responses

Return a `dict`, a `list` or a Pydantic model. **The return value is validated against the
return annotation and then serialised**:

```python
@get("/books/{book_id}")
async def get_book(self, book_id: int) -> Book: ...
```

`/docs` promises callers a response of that shape, so the framework holds you to it: returning
something that does not match the declaration is a **server-side bug** — it becomes a 500 with
the details in the server log, rather than quietly going out on the wire.

### Status codes

```python
@post("/books", status_code=201)
async def create(self, body: NewBook) -> Book: ...


@delete("/books/{book_id}", status_code=204)
async def remove(self, book_id: int) -> None: ...
```

`204` and `304` carry no body per the HTTP spec, so the framework sends an empty response.

When the status code depends on the outcome, build a `Response` yourself — its own status wins:

```python
from starlette.responses import JSONResponse, StreamingResponse


@get("/export")
async def export(self) -> StreamingResponse:      # SSE, downloads, background tasks
    return StreamingResponse(rows())
```

## How errors become responses

Exceptions have three fixed outcomes, all built in — nothing to register, and nothing you can
register:

| Situation | Result |
|---|---|
| the request cannot satisfy the signature (missing parameter, body is not JSON, field validation) | **422**, `{"detail": ...}` |
| `raise HTTPError(status, detail)` | that status code |
| anything else | **500**, `{"detail": "Internal Server Error"}`, traceback in the server log |

`HTTPError` is the only way to produce a 4xx / 5xx from deep in your code — use it when the
request itself should not stand (no permission, not signed in, the resource really is not there):

```python
from canary_framework.web import HTTPError


@get("/books/{book_id}")
async def get_book(self, book_id: int) -> Book:
    book = self.repo.find(book_id)
    if book is None:
        raise HTTPError(404, "no such book")
    return book
```

**Do not express expected business failures as exceptions.** Those belong in the return value —
a `code` field in a uniform response envelope, for instance. The framework takes no part in
business semantics; it only handles "the request never stood" and "the server blew up".

Domain errors should not subclass `HTTPError`: that would teach your domain layer about HTTP.
Translate them in the handler instead.

## Prefixes

`@web_cocoa(prefix="/api")` gives every route of that unit a common prefix.

**The prefix is absolute**, independent of who depends on the unit:

```python
@web_cocoa(prefix="/admin")
class AdminRouter:
    @get("/dashboard")
    async def dashboard(self) -> dict: ...


@web_cocoa(prefix="/api", deps=[AdminRouter])
class ApiRouter:
    @get("/users")
    async def users(self) -> list[dict]: ...
```

```text
GET /api/users            → ApiRouter.users
GET /admin/dashboard      → AdminRouter.dashboard     ← not /api/admin/dashboard
```

Dependencies say what starts first and who may call whom; URLs say how resources are named to the
outside world. Two different things, and neither should decide the other. Want `/api/admin`?
Write `prefix="/api/admin"`.

Prefixes are normalised: `"api"`, `"/api/"` and `" api "` all become `/api`.

## Documentation

The routes of every `@web_cocoa` unit are merged into one app with a single `/openapi.json` and
`/docs`; `title` and `version` come from the outermost unit (nearest the root). Two routes
resolving to the same `METHOD + path` raise `RouteRegistrationError` during startup.

Documentation metadata is pure declaration with no runtime effect:

```python
@web_cocoa(prefix="/api", tags=["library"], title="Library API", version="1.0.0")
class LibraryAPI:
    @get("/books", tags=["read"], summary="List every book")
    async def list_books(self) -> list[Book]:
        """A longer explanation goes in the docstring — it becomes the OpenAPI description."""

    @get("/legacy", deprecated=True)
    async def legacy(self) -> dict: ...
```

`tags` can be written at both levels: the unit's are common tags and the route's are appended
(above, `/api/books` has `["library", "read"]`). `summary` defaults to the method name.

## Routes must live on a web unit

`@get` is only collected on a `@web_cocoa` unit. Written on a plain `@cocoa` it raises
`DeclarationError` at assembly — it used to fail silently: the decorator applied, nothing was
reported, and the route simply was not there.

## Lifecycle

`Canary` drives web apps through the same explicit `init()` / `start()` / `stop()`. Under uvicorn
the ASGI lifespan runs `init()` + `start()` at startup and `stop()` at shutdown. `@web_cocoa`
only adds a route marker on top of `@cocoa`; injection and hooks behave identically.

Signatures are compiled **at assembly time** into a value-fetching plan (where each parameter
comes from, which validator to use, how to serialise the return value), so the request path does
no reflection at all — no re-resolving type hints, no rebuilding `TypeAdapter`s. Dispatch and the
document read the same plan, so the documented binding behaviour and the actual behaviour cannot
drift apart.

## Testing

The optional `test` extra brings in `httpx2`, which Starlette 1.x's `TestClient` uses:

```bash
pip install "canary-framework[web,test]"
```

```python
from starlette.testclient import TestClient
from canary_framework import Canary
from canary_framework.web import get, web_cocoa


@web_cocoa
class LibraryAPI:
    @get("/books")
    async def list_books(self) -> list[dict]:
        return []


def test_list_books() -> None:
    with TestClient(Canary(LibraryAPI)) as client:   # `with` drives the lifespan
        assert client.get("/books").json() == []
```

## Reference

| Name | Purpose |
|---|---|
| `@web_cocoa(deps=[...], prefix="", tags=(), title=..., version=...)` | mark a class as a route holder (`@cocoa` + web marker); `prefix` is absolute |
| `@get` / `@post` / `@put` / `@patch` / `@delete` `(path, *, status_code=200, tags=(), summary=None, deprecated=False)` | mark a method as a request handler |
| `@route(method, path, ...)` | the generic form of the five above |
| `Header(description=None, alias=None)` / `Cookie(...)` | header / cookie parameters, inside `Annotated` |
| `HTTPError(status_code, detail=None, headers=None)` | an error that already is an HTTP concept |
| `WebError` / `RouteRegistrationError` / `RequestValidationError` | the extension's error types |

## Deliberately not provided

Each of these is reasonable on its own; together they are a rewrite of FastAPI — and this
framework's difference is in DI and lifecycle, not in the web layer:

per-request dependency injection (`Depends`) · router nesting (`include_router`) · a middleware
system · WebSocket · forms and file uploads · a `response_model=` parameter (the return
annotation is enough) · multi-status documentation (`responses={}`)

When you need them, Starlette is right there — build a `Response` yourself, or treat `Canary` as
a pure DI and lifecycle container and route with something else.
