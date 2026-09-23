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
| `await unit.stop()` | Stop this unit, then the dependencies nothing else still needs. |

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
every such action into a phase that is reclaimed when the unit stops.

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
lifecycle as its own type: its own hooks run, and the dependencies it declares enter first.

Providing is refused once the scope already holds a `Database`, and when the instance is not a
`Database`. Assigning to a dependency attribute (`service.database = ...`) raises
`AttributeError`: it would change only that one attribute, leaving the rest of the graph on
the original.

## `stop()` is a unit action {#stop-is-a-unit-action}

All three actions belong to the unit they are called on, and `stop()` mirrors `start()`:

| | Order | Across the graph |
|---|---|---|
| `start()` | dependencies first, then the unit | pulls up what the unit needs |
| `stop()` | the unit first, then its dependencies | takes down what nothing else still uses |

`stop()` stops the unit unless something still uses it — a dependent that is starting, running
or stopping — and then tries each of its dependencies the same way. Stopping the root takes
the whole graph down, because nothing else uses its dependencies:

```python
await service.stop()        # service, then database and cache, then config
```

A dependency shared with a unit that is still running stays up:

```python
await root.left.start()
await root.right.start()    # both use Shared
await root.left.stop()      # left stops; shared stays, right still needs it
await root.right.stop()     # right, then shared
```

Stopping a unit that is still in use skips it without an error. Its dependencies are still
tried, and they are in use by it, so nothing stops:

```python
async with service:
    await service.database.stop()    # service still uses database: nothing happens
```

Stopping a unit and its user at the same time stops each unit once. The scope holds the whole
dependency graph, so it always knows who still uses a unit.
