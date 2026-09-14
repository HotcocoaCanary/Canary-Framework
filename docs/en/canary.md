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

To swap an instance in the graph, assign the attribute:

```python
service = UserService()
await service.init()
service.database = FakeDatabase()
```

## `stop()` is a graph action

`init()` and `start()` are unit actions: they advance down the dependencies. `stop()` is
different — it reclaims the whole scope's ledger, so calling it on any unit in the graph has
the same effect.

```python
await service.database.stop()     # reclaims the whole graph, not just database
```

Reclamation cannot be divided: `Database` may be depended on by several units, and stopping it
alone would break the ones still using it.
