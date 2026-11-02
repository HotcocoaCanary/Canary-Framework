# Web application

`canary_framework.web.asgi.app` is a small web framework: routers are units, the application
is a unit, and the application unit **is itself an ASGI application**. It stands on the
application side of the ASGI protocol and depends only on pydantic.

```bash
pip install "canary-framework[app]"        # the application only
pip install "canary-framework[web]"        # the application + this framework's server unit
```

It has no dependency-injection system — dependencies are `dep()`. It generates no OpenAPI,
but it exposes [the endpoint table](#endpoints), from which writing one takes a few
dozen lines.

## Who serves it

The two sides of ASGI know only the protocol, so they combine freely:

| Application | Server | How |
|---|---|---|
| this package's `App` | this framework's [`Server`](server.md) | `class Gateway(Server): api = dep(LibraryApi)` |
| this package's `App` | uvicorn, hypercorn, … | `app = LibraryApi()`, then `uvicorn main:app` |
| FastAPI or another framework | this framework's [`Server`](server.md) | `self.app = fastapi_app` in the `Server`'s `@init` |

In the first, Canary drives the graph and listening is part of the lifecycle. In the second,
the server's lifespan messages drive it: on startup the application unit and its dependencies
`init` and `start` in order, on shutdown they are reclaimed in reverse — so `--reload` and
`--workers` work as usual:

```python
# main.py
app = LibraryApi()
```

```bash
uvicorn main:app --reload
```

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable; see
    [Versioning & Compatibility](../versioning.md#extensions).

## A complete example

```python
import asyncio

from canary_framework import dep
from canary_framework.web.asgi.app import App, Request, Response, Router, error, get, post
from canary_framework.web.asgi.server import Server


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


class Gateway(Server):
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
- A parameter without an annotation is a `str`; a `body` without one is any JSON.
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
        body = {"code": exc.status, "msg": exc.detail}
        return Response.json(body, status=exc.status, headers=exc.headers)
```

An `HTTPError` may carry headers — the `Allow` of a 405 is in `exc.headers` — so a handler
of your own has to pass them on.

Handlers belong to the application. A router mounted under two applications has its
exceptions handled by each application's own handlers, and an application without one answers
in the default way.

An exception with no handler is answered with 500 and logged to the
`canary_framework.web.asgi.app` logger; the response carries no internal detail.

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

## WebSocket

`@websocket` marks a method as a WebSocket endpoint, written in the same router as HTTP
endpoints:

```python
from canary_framework.web.asgi.app import Router, WebSocket, websocket


class RoomApi(Router, prefix="/rooms"):
    rooms = dep(RoomService)

    @websocket("/{room}")
    async def chat(self, socket: WebSocket, room: str, name: str = "guest") -> None:
        async for message in socket:
            await socket.send(f"{name}@{room}: {message}")
```

- Paths and parameters work as for HTTP endpoints: path and query parameters are bound and
  validated; a parameter annotated `WebSocket` is the connection itself. There is no request
  body and no `Request` parameter — read headers from `socket.headers`.
- It must be `async def`; its return value is ignored.
- One path may have both an HTTP endpoint and a WebSocket endpoint; each answers its own kind.

The connection:

| | |
| --- | --- |
| `await socket.receive()` | the next message: `str` for a text frame, `bytes` for a binary one |
| `async for message in socket` | every message, ending normally when the client leaves |
| `await socket.send(data)` | a `str` as a text frame, `bytes` as a binary one |
| `await socket.send_json(data)` | JSON in a text frame; pydantic models and dataclasses work |
| `await socket.accept(subprotocol, headers=...)` | accept the handshake |
| `await socket.close(code, reason)` | close; before accepting, this refuses the handshake |
| `headers`, `query`, `path_params`, `closed` | the first three as on `Request`; `closed` once it is closed |

The handshake is accepted on the first receive or send; call `accept` yourself only to pick a
subprotocol or add response headers. Parse JSON messages yourself, e.g.
`Note.model_validate_json(await socket.receive())`.

Once the client has left, receiving and sending raise `WebSocketClosedError`. An endpoint need
not catch it — the framework treats it as a normal end; use `try` / `finally` for cleanup.

### Handshake and errors

An exception raised before the handshake is accepted — no matching path (404), a failed
validation (422), an `HTTPError` of your own — is answered with the same error response as an
HTTP endpoint when the server supports it (uvicorn does), and otherwise refuses the handshake
(the client sees 403). So authentication is a check before the first receive or send:

```python
@websocket("/admin")
async def admin(self, socket: WebSocket, token: str) -> None:
    if not self.auth.check(token):
        raise HTTPError(403, "bad token")
    ...
```

After accepting, an `HTTPError` closes with 1008, and any other exception closes with 1011 and
is logged. If the endpoint returns with the connection still open, it is closed with 1000.
`@error` handlers apply to HTTP endpoints only.

When the server unit stops, uvicorn closes connected clients with 1012, which ends endpoints
that are receiving or sending. An endpoint waiting a long time on something else keeps
`@stop` waiting, so set `timeout_graceful_shutdown` on the server; see
[Web server](server.md).

The server needs a WebSocket implementation: `canary-framework[server]` brings `wsproto`. When
handing the application to a uvicorn you installed yourself, install `wsproto` and pass
`--ws wsproto` — uvicorn's default websockets-sansio logs a spurious error when a handshake is
refused; see [Web server](server.md).

## The endpoint table { #endpoints }

After `@init`, `App.endpoints` is every endpoint of the application, flattened and read-only.
Each `Endpoint` describes one:

| Attribute | Meaning |
| --- | --- |
| `method`, `path` | the HTTP method (`"WEBSOCKET"` for a WebSocket endpoint) and the full path template, prefixes included |
| `status` | the status of a successful answer; a method returning `None` is answered with 204 when this is 200 |
| `call`, `name` | the bound method itself — its docstring is there — and its qualified name, such as `ReaderApi.show` |
| `params` | the parameters; each `Param` has `name`, `source` (`"path"` / `"query"` / `"body"` / `"request"` / `"websocket"`), `annotation`, `default` and `required` |
| `returns` | the return annotation; `Any` when there is none, `type(None)` for `-> None` |

The application's own endpoints come first, then those of the routers it depends on, in
declaration order. The HEAD that a GET answers is not listed separately.

This package generates no OpenAPI, but the table holds everything needed to write it, and
pydantic translates the types into JSON Schema. This function produces an OpenAPI 3.1
document:

```python
import inspect
from typing import Any

from pydantic import TypeAdapter

from canary_framework.web.asgi.app import Endpoint, Response


def openapi(endpoints: tuple[Endpoint, ...], title: str, version: str = "0.1.0") -> dict[str, Any]:
    schemas: dict[str, Any] = {}

    def schema(annotation: Any, mode: Any = "validation") -> dict[str, Any]:
        found = TypeAdapter(annotation).json_schema(
            ref_template="#/components/schemas/{model}", mode=mode
        )
        schemas.update(found.pop("$defs", {}))
        return found

    paths: dict[str, Any] = {}
    for endpoint in endpoints:
        if endpoint.method == "WEBSOCKET":
            continue  # OpenAPI does not describe WebSocket
        operation: dict[str, Any] = {"operationId": endpoint.name}
        if endpoint.call.__doc__:
            operation["summary"] = inspect.cleandoc(endpoint.call.__doc__).splitlines()[0]
        operation["parameters"] = [
            {"name": p.name, "in": p.source, "required": p.required, "schema": schema(p.annotation)}
            for p in endpoint.params
            if p.source in ("path", "query")
        ]
        for p in endpoint.params:
            if p.source == "body" and p.annotation is not bytes:
                content = {"application/json": {"schema": schema(p.annotation)}}
                operation["requestBody"] = {"required": p.required, "content": content}
        if endpoint.returns is type(None):
            status = 204 if endpoint.status == 200 else endpoint.status
            operation["responses"] = {str(status): {"description": "No Content"}}
        elif endpoint.returns in (Any, Response):
            operation["responses"] = {str(endpoint.status): {"description": "OK"}}
        else:
            content = {"application/json": {"schema": schema(endpoint.returns, "serialization")}}
            operation["responses"] = {
                str(endpoint.status): {"description": "OK", "content": content}
            }
        paths.setdefault(endpoint.path, {})[endpoint.method.lower()] = operation
    return {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version},
        "paths": paths,
        "components": {"schemas": schemas},
    }
```

An application's own methods can be endpoints too, so publishing the document takes a few
lines. A subclass's `@init` runs after the table is built:

```python
class LibraryApi(App):
    api = dep(Api)

    @init
    def describe(self) -> None:
        self.document = openapi(self.endpoints, "Library")

    @get("/openapi.json")
    async def spec(self) -> dict[str, Any]:
        return self.document
```

For a Swagger UI page, point any static documentation page at `/openapi.json`. Two models
with the same name from different modules overwrite each other in `components.schemas`;
rename one when that happens.

## What fails at startup

These raise `DeclarationError` at `@init` or when the class is defined, rather than when a
request arrives:

- two endpoints for the same method and path;
- a path parameter with no parameter to receive it;
- a parameter that looks like a request body (a pydantic model, a dataclass, a `dict`) and
  is not called `body`;
- `*args` / `**kwargs`, or an annotation that cannot be resolved or validated;
- a prefix that does not start with `/`, or ends with one;
- a WebSocket endpoint that is not `async def`, or has a `body` or `Request` parameter; an HTTP
  endpoint with a `WebSocket` parameter.

## What it does not do

Generating OpenAPI and serving documentation pages ([the endpoint table](#endpoints)
is enough to write your own), forms and file uploads, static files, background tasks.

## Testing

Use [`running`](test.md) as for any unit. Without a network:

```python
async with running(LibraryApi) as api:
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readers/7")
```

Over a real socket: write `port = 0` on a subclass of `Gateway`; see [Web server](server.md).

httpx does not speak WebSocket, so test WebSocket endpoints over a real socket, with
`websockets` as the client:

```python
async with running(Gateway) as gateway:     # a subclass of Gateway with port = 0
    async with websockets.connect(f"ws://127.0.0.1:{gateway.port}/rooms/a") as client:
        await client.send("hi")
        assert await client.recv() == "guest@a: hi"
```
