# ASGI

`canary_framework.asgi` splits "application" and "listening" into two kinds of unit:

- **`App`** is an application unit: one ASGI application that does not listen.
  The `App` of [`asgi.fastapi`](fastapi.md) is one.
- **`Server`** is the unit that listens: one per port, serving the application units it
  depends on directly.

Applications are values and there can be many; what has to be unique is the port. So however
many services a process holds, there is one listener.

```bash
pip install "canary-framework[asgi]"
```

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable — see
    [Versioning & Compatibility](../versioning.md#extensions).

## One port, several applications

```python
from canary_framework import asgi, dep


class Gateway(asgi.Server):
    api = dep(LibraryApi)           # a FastAPI application unit, answering /
    metrics = dep(Metrics)          # another application unit, answering /metrics

    host = "0.0.0.0"
    port = 8010


async with Gateway():
    ...
```

**Depending is serving**: the application units a `Server` depends on directly are all on its
port, each answering its own `path`. It is the same rule as for routers.

| Phase | What `Server` does |
|---|---|
| `@start` | Binds the port and starts serving. Everything it depends on has started by now |
| `@stop` | Stops accepting connections and waits for requests in flight |

Applications are the depended-on side, so their `@start` comes before listening and their
`@stop` after closing — and so does the database's. That is just dependency order; nothing else
has to be arranged.

A port in use makes `start()` raise `OSError`, and the dependencies that started are reclaimed
as usual. `port = 0` lets the system pick one; once serving, `server.port` is the actual port.
Two applications with the same `path` make `start()` raise `LifecycleError`.

One application unit may be depended on by two `Server`s — a public port and an internal one,
say; it is still a single instance.

## How paths are dispatched

A request goes to the application with the **longest matching prefix**, matched by whole
segments: `/api` answers `/api` and `/api/...` but not `/apix`; `/` answers everything else.
With no match, HTTP gets a 404.

Requests are forwarded, not rewritten: the application still sees the full path, so its own
routes must include the prefix. This is not "mounting" in Starlette's sense.

## An application unit of your own

Any ASGI application can be an application unit; assign it to `self.app` in `@init`:

```python
class Metrics(asgi.App):
    registry = dep(Registry)

    path = "/metrics"

    @init
    def build(self) -> None:
        self.app = make_asgi_app(self.registry)
```

## Assembling by hand

Assign `self.app` in a `Server`'s `@init` and that is what it serves; the application units it
depends on are no longer added automatically. `dispatch` is the same function the automatic
assembly uses:

```python
class Gateway(asgi.Server):
    api = dep(LibraryApi)
    port = 8010

    @init
    def build(self) -> None:
        self.app = asgi.dispatch({"/legacy": legacy_wsgi_bridge, "/": self.api.app})
```

## Canary owns the process

The lifecycle is driven by Canary, so:

- ASGI lifespan is off. Whatever startup and cleanup an application needs belongs in its
  unit's `@start` / `@stop`;
- the server does not take over signals; the entry point decides when to exit;
- there is no `uvicorn main:app`, hence no `--reload` or `--workers`. Run several processes
  with container replicas or a process manager.

An entry point that reacts to signals:

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
