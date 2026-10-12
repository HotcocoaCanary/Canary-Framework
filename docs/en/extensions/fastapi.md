# FastAPI

`canary_framework.asgi.fastapi` expresses HTTP as units: a router is a unit, and so is the FastAPI
application, which a [`canary_framework.asgi`](asgi.md) server listens for. Parameter parsing,
validation, serialisation and OpenAPI are all [FastAPI](https://fastapi.tiangolo.com/)'s. It is a
subpackage of `asgi` and builds on it.

```bash
pip install "canary-framework[fastapi]"
```

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable — see
    [Versioning & Compatibility](../versioning.md#extensions).

## A complete example

```python
import asyncio

from canary_framework import Canary, asgi, dep
from canary_framework.asgi.fastapi import App, Router, get, post


class ReaderApi(Router, prefix="/readers", tags=["readers"]):
    readers = dep(ReaderService)

    @get("")
    async def search(self, keyword: str | None = None) -> list[Reader]:
        return await self.readers.search(keyword)

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return await self.readers.get(reader_id)

    @post("", status_code=201)
    async def create(self, body: NewReader) -> Reader:
        return await self.readers.create(body)


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)
    loans = dep(LoanApi)


class LibraryApi(App, title="Library API", version="1.0.0"):
    api = dep(Api)


class Gateway(asgi.Server):
    library = dep(LibraryApi)

    host = "0.0.0.0"
    port = 8010


async def main() -> None:
    async with Gateway():
        await asyncio.Event().wait()


asyncio.run(main())
```

## Route marks

`get` / `post` / `put` / `patch` / `delete` / `head` / `options` / `trace` / `api_route` /
`websocket` are the decorators of FastAPI's `APIRouter` by the same names: the same
parameters and defaults, so your IDE's completion and FastAPI's documentation apply as they
are. There is one difference — they only record the call on the method and leave the method
alone; when the application starts, the call is replayed on a real `APIRouter`, decorating the
**bound method**.

- Everything you know from FastAPI works: `response_model`, `status_code`, `dependencies`,
  `Depends`, `WebSocket`, …
- The path is required, as in FastAPI. `""` is the router's prefix itself: `@get("")` above
  is `GET /api/readers`; an application's own endpoints have no prefix, so its root is `"/"`.
- Endpoints are bound methods, so dependencies between units are the `dep()`s on `self`;
  per-request things can still use `Depends`.

It differs from plain FastAPI in two ways only, and they are why this package exists:
endpoints are methods of units, and routers are aggregated by dependency rather than
`include_router`. For a different and smaller web layer, see [`asgi.web`](web.md).

!!! warning "Do not name a method `get`"
    A method called `get` in the class body shadows the `@get` that follows it. Give the
    method another name.

Marks resolve by **attribute name**, like lifecycle hooks: overriding a method replaces it, and
an override that is no longer marked is no longer an endpoint.

## Router units

A `Router` is a unit with a prefix and tags. **Aggregation is dependency**: `dep()` a router
and it is mounted under you, prefixes adding up level by level. The route tree is the
dependency graph; there is no separate registration step.

It is still an ordinary unit:

- it has its own dependencies and hooks;
- its endpoints are ordinary methods, so a test can `await api.show(3)` without HTTP;
- it is not FastAPI's `APIRouter`, so no method or attribute name can collide with FastAPI.

Class parameters other than `prefix` and `tags` go to `APIRouter` unchanged. A subclass
inherits its parent's class parameters and overrides only the ones it writes.

Two rules:

- A router is mounted only when an `App` or another router depends on it **directly**.
- A router depended on from two places appears under both prefixes, backed by one instance.

## The application unit

`App` is an [`asgi.App`](asgi.md): its `@init` builds the FastAPI app `self.app` and mounts
its own endpoints and the routers it depends on directly. Its class parameters go to
`FastAPI(...)` unchanged.

It does not listen. Whichever `asgi.Server` depends on it directly serves it on that port, and
other application units can share the port. A process usually needs one `App`, so there is
one OpenAPI document too.

### Configuring the app

A subclass's `@init` runs after the app is built and before anything is served, so middleware
and exception handlers are still in time:

```python
class LibraryApi(App, title="Library API"):
    api = dep(Api)

    @init
    def setup(self) -> None:
        self.app.add_exception_handler(DomainError, self.on_domain_error)

    async def on_domain_error(self, _: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"msg": str(error)}, status_code=400)
```

`self.app` is the FastAPI application, used exactly as usual.

### With a FastAPI app you already have

To use only the router units and keep your own app and server, `mount` (imported from `canary_framework.asgi.fastapi` too) puts a graph's
routes on it:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Library() as root:       # Library depends on some Routers
        mount(root, app)
        yield


app = FastAPI(lifespan=lifespan)
```

The lifecycle belongs to Canary rather than uvicorn; the entry point and the trade-offs are
described under [ASGI](asgi.md).

## Testing

Use `port = 0` to go through a real socket:

```python
class TestGateway(Gateway):
    port = 0


async with running(TestGateway) as gateway, httpx.AsyncClient() as client:
    response = await client.get(f"http://127.0.0.1:{gateway.port}/api/readers/7")
```

Or skip the network and the server altogether, and call the application unit:

```python
async with running(LibraryApi) as api:
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readers/7")
```

Units are replaced as in any other test — with the second argument of [`running`](test.md).
