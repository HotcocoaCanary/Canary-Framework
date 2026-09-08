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
| `await app.start()` | `INITIALIZED → STARTED` | run `@on_start` in order, then merge every `@web_cocoa` unit's routes into one serving app |
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
logger — start order, each unit's dependencies, and the mounted routes. No need to read the
framework's source to find out why a route is missing or why a unit started first:

```text
Canary assembled 4 unit(s)
  roots: LibraryApp
  start order (stop runs in reverse):
    1. Config
    2. Database  <- Config
    3. BookRepository  <- Database
    4. LibraryApp  <- BookRepository
  routes:
    GET    /api/books  -> LibraryApp.list_books
```

## Serving ASGI

`Canary` is itself an ASGI app. Its `__call__(scope, receive, send)` handles the `lifespan` scope
to drive `init()` / `start()` / `stop()`, and delegates every other scope (`http`, `websocket`,
…) to the **single serving app** merged from all `@web_cocoa` units:

```python
from canary_framework import Canary

app = Canary(LibraryAPI)  # `app` is the ASGI app

# uvicorn examples.library.web:app
```

The whole composition exposes exactly one `/openapi.json` and one `/docs`. The import of the web
extension is **lazy** — it happens only when the graph actually contains a `@web_cocoa` unit, so
a pure `@cocoa` composition never needs `canary-framework[web]` installed.

Without a lifespan (for example when you call `app` directly), the first request starts the app,
and concurrent first requests queue for that single startup. That path is a fallback; in a real
deployment let the server's lifespan drive it.

How routes are merged and how the lazy import is wired is described in
[Architecture](architecture.md).
