# Web

`canary_framework.asgi.web` is a small web framework whose routers and application are units,
listened for by a [`canary_framework.asgi`](asgi.md) server. It is a subpackage of `asgi` and
depends only on pydantic.

```bash
pip install "canary-framework[web]"
```

It has no dependency-injection system — dependencies are `dep()` — and generates no OpenAPI.
For OpenAPI or the FastAPI ecosystem use [`asgi.fastapi`](fastapi.md); the two packages sit
side by side, and are written alike but not the same.

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable; see
    [Versioning](../versioning.md#extensions).

## A complete example

```python
import asyncio

from canary_framework import asgi, dep
from canary_framework.asgi.web import App, Request, Response, Router, error, get, post


class ReaderApi(Router, prefix="/readers"):
    readers = dep(ReaderService)

    @get
    async def search(self, keyword: str | None = None, limit: int = 20) -> list[Reader]:
        return await self.readers.search(keyword, limit)

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return await self.readers.get(reader_id)

    @post(status=201)
    async def create(self, body: NewReader) -> Reader:
        return await self.readers.create(body)


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)
    loans = dep(LoanApi)


class LibraryApi(App):
    api = dep(Api)

    @error(DomainError)
    async def on_domain_error(self, request: Request, exc: DomainError) -> Response:
        return Response.json({"msg": exc.message}, status=exc.code)


class Gateway(asgi.Server):
    library = dep(LibraryApi)
    port = 8010


async def main() -> None:
    async with Gateway():
        await asyncio.Event().wait()


asyncio.run(main())
```

## Routing

A `Router` is a unit with a prefix, and `get` / `post` / `put` / `patch` / `delete` mark its
methods as endpoints. **Aggregation is dependency**: `dep()` a router and it is mounted under
you, prefixes adding up level by level.

- With the path omitted, the endpoint is the unit's prefix itself: `@get` above is
  `GET /api/readers`.
- `{name}` is a path parameter and takes a whole segment.
- The status of a successful answer goes on the mark: `@post(status=201)`.
- A router is mounted only when an `App` or another router depends on it **directly**;
  depended on from two places, it appears under both prefixes, backed by one instance.
- An endpoint is an ordinary method: a test can `await api.show(3)` without HTTP.

!!! warning "Do not name a method `get`"
    A method called `get` in the class body shadows the `@get` that follows it. Give the
    method another name.

### Matching

At `@init` the application flattens every endpoint into one table:

- a path without parameters wins over one with: `/books/new` before `/books/{book_id}`;
- between two with parameters, the leftmost static segment wins: `/a/b/{y}` before
  `/a/{x}/c`;
- a trailing slash matters, and nothing is redirected;
- `HEAD` is answered by `GET` when it has no endpoint of its own.

## How parameters are bound

A parameter is classified in this order:

| Parameter | Comes from |
|---|---|
| annotated `Request` | the request object |
| named in the path template | the path |
| named `body` | the JSON request body; raw bytes when annotated `bytes` |
| anything else | the query string |

- The body is recognised **by name**: only the parameter called `body` is the request body,
  so an endpoint has at most one.
- A query parameter with a default is optional; annotated `list[...]` or the like, it takes
  every value given under that name (`?tag=1&tag=2`).
- A parameter without an annotation is a `str`.
- Validation and conversion are pydantic's, so any type it validates can be used. The body
  goes through its JSON mode, which validates the raw bytes — so a `strict=True` model still
  accepts the strings JSON has for dates, UUIDs and the like.
- Headers and cookies get no annotation magic: take a `request: Request` and read them.

A failed validation is answered with 422, reporting every failed parameter at once:

```json
{"detail": [{"loc": ["query", "limit"], "msg": "Input should be a valid integer, ...", "type": "int_parsing"}]}
```

## Sync and async

- An `async def` endpoint runs on the event loop.
- A plain `def` endpoint runs in a thread pool (`asyncio.to_thread`), so the blocking calls
  inside it — a synchronous database driver, `requests`, file access — do not hold other
  requests.

The same goes for a handler marked with `@error`. Two things to keep in mind: a blocking call
inside an `async def` still stalls the whole process; and a method in the thread pool runs
concurrently with the event loop, so it must take care of its own thread safety when it
touches state on a unit.

## Return values and responses

| Returned | Answer |
|---|---|
| a `Response` | sent as it is |
| `None` | empty, 204 (or the `status` written on the mark) |
| anything else | serialised to JSON by the return annotation |

The return annotation is used to serialise only; the returned value is not validated again.

A `Response` is for deciding the status, the headers and the content type yourself:

```python
return Response("pong")                                     # plain text
return Response.json({"id": 7}, status=201, headers={"location": "/readers/7"})
return Response(self.events(), media_type="text/event-stream")   # an async iterator: streamed
```

## Errors

```python
raise HTTPError(404, "no such reader")
```

`HTTPError` can be raised in an endpoint, a service, or anything they call, and is answered
with `{"detail": ...}`. A path nobody answers (404), a method nobody answers (405, with an
`Allow` header) and a failed validation (422) are `HTTPError` too.

`@error(ExceptionType)` marks a method of the application as a handler. An exception goes to
the handler of the closest type, and what the handler returns is treated like an endpoint's
return value:

```python
class LibraryApi(App):
    @error(HTTPError)
    def envelope(self, request: Request, exc: HTTPError) -> Response:
        return Response.json({"code": exc.status, "msg": exc.detail}, status=exc.status)
```

An exception with no handler is answered with 500 and logged to the
`canary_framework.asgi.web` logger; the response carries no internal detail.

## Middleware

An `App`'s `self.app` is an ASGI application. A subclass's `@init` runs after it is built, so
wrapping it is enough, and any ASGI middleware works. This package ships none of its own —
for CORS and the like use an existing ASGI middleware, such as Starlette's `CORSMiddleware`:

```python
class LibraryApi(App):
    api = dep(Api)

    @init
    def wrap(self) -> None:
        self.app = CORSMiddleware(self.app, allow_origins=["*"])
```

## What fails at startup

These raise `DeclarationError` at `@init` or when the class is defined, rather than when a
request arrives:

- two endpoints for the same method and path;
- a path parameter with no parameter to receive it;
- a parameter that looks like a request body (a pydantic model, a dataclass, a `dict`) and
  is not called `body`;
- `*args` / `**kwargs`, or an annotation that cannot be resolved or validated;
- a prefix that does not start with `/`, or ends with one.

## What it does not do

OpenAPI, WebSocket, forms and file uploads, static files, background tasks.

## Testing

Use [`running`](test.md) as for any unit. Without a network:

```python
async with running(LibraryApi) as api:
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readers/7")
```

Over a real socket: write `port = 0` on a subclass of `Gateway`; see [ASGI](asgi.md).
