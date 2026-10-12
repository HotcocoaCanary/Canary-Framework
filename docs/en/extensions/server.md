# Web server

The `Server` of `canary_framework.web.asgi.server` is a unit that listens on a port: listening
is its `@start`, closing is its `@stop`. It stands on the server side of the ASGI protocol and
serves **any** ASGI application — this framework's [application unit](app.md), a FastAPI
object, a hand-written `async def app(scope, receive, send)`.

```bash
pip install "canary-framework[server]"
```

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable; see
    [Versioning](../versioning.md#extensions).

## Depending is serving

```python
from canary_framework import dep
from canary_framework.web.asgi.server import Server


class Gateway(Server):
    api = dep(LibraryApi)           # an application unit, answering /
    metrics = dep(Metrics)          # another, answering /metrics

    host = "0.0.0.0"
    port = 8010


async with Gateway():
    ...
```

Among the units a `Server` depends on directly, one that is **callable and declares a `path`**
is an application, served on its port under that `path`. Both are required: a database or the
settings are not callable; a strategy object that happens to define `__call__` has no `path` —
they are ordinary dependencies.

| Phase | What `Server` does |
|---|---|
| `@start` | Binds the port and starts serving. Everything it depends on has started |
| `@stop` | Stops accepting connections and waits for requests in flight |

Applications are depended on, so their `@start` runs before listening and their `@stop` after
closing — and so does the database's. That is dependency order; nothing else arranges it.

- A port in use makes `start()` raise `OSError`, and what had started is reclaimed as usual.
- `port = 0` lets the system pick one. While serving, `server.port` is the actual port; after
  stopping it is 0 again, so a restart asks for a new one.
- Two applications with the same `path` make `start()` raise `LifecycleError`.
- One application unit can be depended on by two `Server`s — a public port and an internal
  one, say — and is still a single instance.

## A hand-written application unit

A unit that is callable and declares a `path` is an application unit; there is nothing to
inherit:

```python
class Metrics(Canary):
    registry = dep(Registry)

    path = "/metrics"

    async def __call__(self, scope, receive, send) -> None:
        await self.registry.asgi_app(scope, receive, send)
```

## An application from another framework

Assign any ASGI application to `self.app` in an `@init` hook. Once assigned it is what gets
served, and the application units depended on are no longer added automatically:

```python
fastapi_app = FastAPI()


class Gateway(Server):
    port = 8010

    @init
    def build(self) -> None:
        self.app = fastapi_app
```

### The application's own lifespan

By default `Server` sends the application no ASGI lifespan messages: starting and reclaiming
belong to Canary's lifecycle. That is a trap when migrating by "changing the server first" —
the connection pool or cache warm-up an old application does in `lifespan` /
`on_event("startup")` **silently does not happen**, while its endpoints still answer. Two ways
out:

- turn it on with a class parameter: `class Gateway(Server, lifespan="on")`. The application
  starts inside the `Server`'s `@start`, before it listens, and is reclaimed inside `@stop`;
  an application that fails to start fails the `Server`'s start, and what had started is
  reclaimed as usual. This framework's application units have already been started by Canary
  by then, so they only acknowledge and are not driven twice.
- or move that part into a unit's `@start` / `@stop` and let the `Server` depend on it — where
  a migration usually ends up.

### Using units from another framework's endpoints

Another framework's endpoints are module-level functions, not methods of units, so their
dependencies cannot be `dep()`s and have to be looked up on the graph per request. With
FastAPI the bridge is a dozen lines:

```python
from canary_framework import Canary
from canary_framework.test import unit
from fastapi import Depends, FastAPI, Request


def attach(app: FastAPI, root: Canary) -> None:
    app.state.graph = root          # called from the Server's @init: attach(fastapi_app, self)


def use[T: Canary](cls: type[T]) -> T:
    async def resolve(request: Request) -> T:       # must be async def
        return unit(request.app.state.graph, cls)

    return Depends(resolve)


@fastapi_app.get("/readers/{reader_id}")
async def show(reader_id: int, readers: ReaderService = use(ReaderService)) -> Reader:
    return await readers.get(reader_id)
```

Two things:

- **Write the dependency function as `async def`.** FastAPI runs a synchronous dependency in
  a thread pool, one more thread switch per request; this one only looks up a dictionary, and
  measured, the synchronous version cuts throughput to a third.
- **Look units up by type with `canary_framework.test.unit`.** It lives in the `test` package,
  but all it does is return a unit of a graph by its type, and using it in production code is
  fine.

## How paths are dispatched

A request goes to the application with the **longest matching prefix**, and prefixes match
whole segments: `/api` answers `/api` and `/api/...`, not `/apix`; `/` answers everything else.
With no match, HTTP gets a 404.

Requests are forwarded, not rewritten: the application still sees the full path, so its own
routes include the prefix. This is not "mounting" in Starlette's sense.

The automatic assembly uses `canary_framework.web.asgi.dispatch`; use it directly to assemble
by hand:

```python
from canary_framework.web.asgi import dispatch


class Gateway(Server):
    api = dep(LibraryApi)
    port = 8010

    @init
    def build(self) -> None:
        self.app = dispatch({"/legacy": legacy_app, "/": self.api})
```

## Configuring uvicorn

`Server` uses uvicorn inside. Class parameters go to `uvicorn.Config` unchanged; a subclass
inherits its parent's and overrides only the ones it writes:

```python
class Gateway(Server, timeout_graceful_shutdown=10, proxy_headers=True):
    api = dep(LibraryApi)
```

`timeout_graceful_shutdown` is worth setting. Without it `@stop` waits until every request in
flight has finished: one long-lived connection that never ends holds the shutdown, the
database and the other dependencies behind it are not reclaimed, and the process ends up
being killed.

`host` and `port` stay class attributes; `app`, `reload` and `workers` belong elsewhere here,
and passing one raises `TypeError` when the class is defined. `lifespan` defaults to `"off"`;
see above.

WebSocket needs an implementation installed separately (`websockets` or `wsproto`); uvicorn
does not bring one.

## Canary owns the process

The lifecycle is driven by Canary, so:

- the server does not take over signals; when to exit is up to the entry point;
- there is no `--reload` or `--workers`. When you need them, do not use `Server`: hand the
  [application unit](app.md) to uvicorn directly.

An entry point that responds to signals:

```python
async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    async with Gateway():
        await stop.wait()
```

A `Server` need not be the root. A daemon that also opens an admin port is one more
`dep(AdminServer)` on its root.

## Testing

```python
class TestGateway(Gateway):
    port = 0


async with running(TestGateway) as gateway, httpx.AsyncClient() as client:
    response = await client.get(f"http://127.0.0.1:{gateway.port}/api/readers/7")
```
