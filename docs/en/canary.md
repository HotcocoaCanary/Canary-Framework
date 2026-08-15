# Runtime (Canary)

`Canary` is the orchestrator that owns a graph of [cocoas](cocoa.md) and drives their
lifecycle. It is not itself a business unit — it only resolves, orders, and runs them.

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

Each root must be decorated with `@cocoa`, otherwise `Canary` raises `TypeError` at
construction. Passing several roots composes their graphs into one shared graph.

## The lifecycle methods

| Method | Transition | What it does |
|---|---|---|
| `await app.init()` | `NEW → INITIALIZED` | build the graph, topologically sort it, run `@on_init` in order |
| `await app.start()` | `INITIALIZED → STARTED` | inject dependencies, run `@on_start` in order, collect the serving app |
| `await app.stop()` | `STARTED → STOPPED` | run `@on_stop` in reverse order |

The engine is async-native: hooks may be sync or async, and the runtime `await`s based on the
returned value. See [Lifecycle](lifecycle.md) for the state machine and error handling.

`Canary` also implements the async context-manager protocol:

```python
async with Canary(UserService) as app:
    assert app[Database] is app[UserService].database
```

## Accessing instances

Use `__getitem__` to fetch the shared singleton of a type in this graph:

```python
users = app[UserService]
assert users.database is app[Database]
```

The `order` property returns the topological startup order (dependencies first); `instances`
returns the corresponding instances in the same order; `state` returns the current
`LifecycleState`.

## Multi-root composition

Because a `Canary` accepts several roots, the same unit can participate in different graphs —
and any sub-tree can be launched on its own:

```python
# Full application
app = Canary(LibraryApp)
await app.start()

# Just the data layer, independently
books = Canary(BookRepository)
await books.start()
```

Dependencies are shared within a single graph but not across two separate `Canary` instances.

## Serving ASGI

`Canary` is itself an ASGI application. Its `__call__(scope, receive, send)` handles the
`lifespan` scope to drive `init()` / `start()` / `stop()`, and delegates every other scope
(`http`, `websocket`, …) to a **serving app** that one of its units exposed during `start()`.

This is how the [web extension](web.md) works: `@web_cocoa` injects an `@on_start` hook that
builds a Starlette app and exposes it under a marker; `Canary` finds it by duck typing and
delegates to it — without importing any concrete extension:

```python
from canary_framework import Canary

app = Canary(LibraryAPI)  # app is the ASGI application

# uvicorn examples.library.web:app
```

See [Architecture](architecture.md) for how this duck-typing is wired.
