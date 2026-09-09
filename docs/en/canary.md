# Runtime (Canary)

`Canary` is the orchestrator that owns a graph of [cocoa](cocoa.md) units and drives their
lifecycle. It is not a business unit itself — it only resolves, orders and runs.

```python
from canary_framework import Canary


app = Canary(UserService)
await app.init()
await app.start()
...
await app.stop()
```

## Construction

```python
app = Canary(*roots)
```

Every root must be marked with `@cocoa`, otherwise `Canary` raises `TypeError` at construction.
Passing several roots merges their graphs into one. `Canary(...)` itself does nothing — the
graph is built in `init()`.

## Lifecycle methods

| Method | Transition | What it does |
|---|---|---|
| `await app.init()` | `NEW → INITIALIZED` | build, validate, sort, **inject dependencies**, run `@on_init` in order |
| `await app.start()` | `INITIALIZED → STARTED` | run `@on_start` in order |
| `await app.stop()` | any settled state `→ STOPPED` | run `@on_stop` in reverse; idempotent, shared by normal and failed termination |

The engine is async-native: hooks may be sync or async and the runtime awaits only when needed.
The state machine and the failure paths are described in [Lifecycle](lifecycle.md).

`Canary` also implements the async context manager protocol:

```python
async with Canary(UserService) as app:
    assert app[Database] is app[UserService].database
```

## Reaching the instances

Use `__getitem__` to get the shared singleton for a type:

```python
users = app[UserService]
assert users.database is app[Database]
```

`order` returns the topological start order (dependencies first), `instances` returns the
instances in the same order, and `state` returns the current `LifecycleState`.

## Multi-root composition

Because `Canary` accepts several roots, the same unit can take part in different graphs — and
any subgraph can be started on its own:

```python
# the whole application
app = Canary(LibraryApp)
await app.init()
await app.start()

# just the data layer
books = Canary(BookRepository)
await books.init()
await books.start()
```

Dependencies are shared inside one graph, never between two independent `Canary` instances.

Multi-root has one consequence worth knowing: **no unit starts last**, so there is no "after
everything is up" position. Declare a single composition root if you need one.

## The assembly summary

Set `CANARY_LOG_LEVEL=DEBUG` and the end of startup prints a summary on the `canary.runtime`
logger — start order and each unit's dependencies. No need to read the framework's source to
find out why a unit started first:

```text
Canary assembled 4 unit(s)
  roots: LibraryApp
  start order (stop runs in reverse):
    1. Config
    2. Database  <- Config
    3. BookRepository  <- Database
    4. LibraryApp  <- BookRepository
```

## Letting a host drive it

`Canary` knows about no shell — it is neither a web framework nor a CLI framework.

Two host protocols, two entry points:

| What the host takes | Use | Who does this |
|---|---|---|
| an async context manager, `Callable[[Host], AsyncContextManager]` | `canary.lifespan` | ASGI (Starlette / FastAPI / Litestar), MCP, FastStream |
| paired startup / shutdown callbacks | `init()` / `start()` and `stop()` | Quart, Sanic, arq, Dramatiq |

```python
app = FastAPI(lifespan=canary.lifespan)          # that is the whole wiring
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
server = MCPServer("demo", lifespan=canary.lifespan)
```

Without a host (a CLI, a script, a test fixture) use it directly:

```python
async with canary.lifespan():
    ...
```

To reach a unit inside a host's handler, `canary[SomeUnit]` is it — dependencies are already
injected, so `self.<dep>` just works. With FastAPI's `Depends` that takes a three-line factory:

```python
def provide[T](cls: type[T]):
    def dep() -> T:
        return canary[cls]
    return dep


@app.get("/books/{book_id}")
async def read(book_id: int, svc: Annotated[LibraryApp, Depends(provide(LibraryApp))]):
    return svc.get_book(book_id)
```

HTTP, WebSocket, static files, middleware and authentication all belong to the host. Canary only
guarantees that your objects are assembled correctly, started in order and reclaimed in reverse.
