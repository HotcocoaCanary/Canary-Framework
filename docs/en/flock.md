# Flock

`Flock` is the optional orchestrator returned by `Canary.run()`. It receives a root Canary and drives the full lifecycle of its transitive dependency graph:

1. discover dependencies,
2. build the dependency graph,
3. topologically sort it,
4. construct one shared instance per Canary type in topological order,
5. run `__aenter__` in topological order,
6. on shutdown or failure, run `__aexit__` in reverse topological order.

`Flock` is not itself a business service — it only orchestrates lifecycle. A Canary can run without one.

## Construction

```python
from canary_framework import canary


@canary
class APIService: ...


flock = APIService.run()
```

The root must be a registered Canary, otherwise `DependencyError` is raised.

## Starting and stopping

```python
await flock.start()
...
await flock.stop()
```

- `start` builds the graph, initializes, and starts every Canary in order.
- `stop` stops running Canaries in reverse order.
- `Flock` also supports the async context-manager protocol:

```python
async with APIService.run() as flock:
    ...
```

## Accessing instances

Use `__getitem__` to fetch the shared instance of a Canary type in this graph:

```python
users = flock[UserService]
assert users.database is flock[Database]
```

The `instances` property returns a copy of the instance mapping, keyed by Canary type. The `order` property returns the topological order (dependencies first).

## Orchestration state

`flock.state` follows `FlockState`:

```
NEW → STARTING → RUNNING → STOPPING → STOPPED
                        └──▶ FAILED
```

## Failure and rollback

If any Canary fails during startup, `Flock` rolls back: it stops every already-running Canary in reverse order, marks in-progress Canaries `FAILED`, sets its own state to `FAILED`, and raises `StartupError` chaining the original exception.
