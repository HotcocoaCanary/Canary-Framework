# Units

A unit is a plain class that subclasses `Canary`. `Canary` does two things: it puts the class
into the dependency graph (so others may `dep()` it), and it gives the class four lifecycle
actions.

```python
from canary_framework import Canary, dep, init, start, stop


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn)

    @stop
    async def close(self) -> None:
        await self.pool.close()
```

Beyond that it stays a plain Python class: it can be subclassed, mixed in and nested.

## The four actions

| Action | What it does |
|---|---|
| `Unit()` | Construct with no arguments. No hooks run; dependencies are not available yet. |
| `await unit.init()` | Advance the `init` phase along dependencies. |
| `await unit.start()` | Advance the `start` phase along dependencies. |
| `await unit.stop()` | Reclaim the ledger in reverse. |

`async with unit` is the convenience form: entering calls `init()` then `start()`, leaving
calls `stop()`. All three go through this class's own methods, so a subclass's overrides apply
on that path too.

## Construction takes no arguments

Units are always constructed by the framework with no arguments, so `__init__` may not have
required parameters:

```python
class Database(Canary):
    def __init__(self, dsn: str) -> None:   # not allowed
        self.dsn = dsn
```

```
ConstructionError: cannot construct Database: missing a required argument: 'dsn'.
Units are always constructed with no arguments. Declare what it needs with dep(...)
and read the values from those dependencies in @init or @start.
```

Turn the constructor argument into a dependency and read the value in a hook:

```python
class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn)
```

The constraint is deliberate: `@start` has a matching `@stop`, while construction has no
matching destructor. Deferring anything that needs the outside world to a lifecycle hook puts
every such action into a phase that is ledgered and can be reclaimed in reverse.

## Any unit can be the entry point

Any unit in the graph can run on its own, and it is then the root of its own graph:

```python
async with BookRepository() as books:      # brings up its Database and Config too
    ...
```

## Overriding and composition

Lifecycle methods are ordinary methods; override them and compose with `super()`:

```python
class Traced(Canary):
    async def start(self) -> None:
        log.info("starting %s", type(self).__name__)
        await super().start()
        log.info("started %s", type(self).__name__)


class Service(Traced):
    @start
    async def go(self) -> None: ...
```

Phase hooks may be named anything, as long as the name does not collide with `init`, `start`,
`stop`, `__aenter__` or `__aexit__`.

## Substitutes

Unit-ness is inherited, so a test double just subclasses what it replaces:

```python
class FakeDatabase(Database):
    @start
    async def connect(self) -> None:
        self.pool = InMemoryPool()
```

To swap it into the graph, provide it to the scope before the lifecycle begins:

```python
from canary_framework import scope_of

service = UserService()
scope_of(service).provide(Database, FakeDatabase())

async with service:
    ...
```

Every `dep(Database)` in the graph now returns that instance, and it takes part in the
lifecycle as its own type: its own hooks run, and the dependencies it declares advance first.

Providing is refused once the scope already holds a `Database`, and when the instance is not a
`Database`. Assigning to a dependency attribute (`service.database = ...`) raises
`AttributeError`: it would change only that one attribute, leaving the rest of the graph on
the original.

## `stop()` is a unit action

All three actions belong to the unit they are called on. `start()` brings up the unit and what
it needs; `stop()` reclaims the unit and whatever nothing else still needs:

```python
await service.stop()       # the root: nothing else needs its dependencies, so the whole graph goes
```

A dependency stays up while something running still needs it — a unit you started directly, or
anything reachable from one through `dep()`:

```python
await root.start()
await root.metrics.start()    # also asked for directly
await root.stop()             # root goes; metrics and what it needs stay up
await root.metrics.stop()     # now they go too
```

Stopping a unit that running units still depend on is refused, and nothing is reclaimed:

```python
await service.database.stop()
```

```
LifecycleError: Database is still required by running units: UserService. Stop those first.
```

The scope knows every declared dependency, so it can tell who still needs a unit; stop those
first, or stop the root.
